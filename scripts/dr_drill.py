#!/usr/bin/env python3
"""
scripts/dr_drill.py

Disaster Recovery Automation & Verification Drill CLI.
Executes automated encrypted backup creation, isolated restore testing,
and Redis failure reconciliation drills.

Usage:
    python scripts/dr_drill.py --action backup --out /tmp/backup.json
    python scripts/dr_drill.py --action restore-drill --snapshot /tmp/backup.json
    python scripts/dr_drill.py --action test-redis-reconcile
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.postgres import Base, get_db
from backend.disaster_recovery.backup import create_backup
from backend.disaster_recovery.reconciliation import (
    reconcile_after_redis_loss,
    verify_isolated_restore,
)
from backend.disaster_recovery.restore import restore_backup
from backend.memory.redis_client import redis_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("dr_drill")


async def run_backup(out_path: str | None) -> None:
    """Creates an encrypted backup snapshot from active DB."""
    async for session in get_db():
        backup = await create_backup(session=session, target_path=out_path)
        manifest = backup["manifest"]
        logger.info("Backup successfully generated!")
        logger.info("Backup ID: %s", manifest["backup_id"])
        logger.info("Total Records: %d", manifest["total_records"])
        logger.info("SHA-256 Checksum: %s", manifest["sha256_checksum"])
        break


async def run_restore_drill(snapshot_path: str) -> None:
    """Restores snapshot into an isolated in-memory target database to test DR viability."""
    logger.info("Starting isolated restore verification drill for snapshot: %s", snapshot_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as drill_session:
        summary = await restore_backup(
            backup_package=Path(snapshot_path),
            target_session=drill_session,
            actor="dr_cli_drill",
        )
        logger.info("Drill restore completed successfully in %.2fs!", summary["duration_seconds"])
        logger.info("Restored table counts: %s", summary["restored_counts"])

    await engine.dispose()


async def run_redis_reconcile_drill() -> None:
    """Tests Redis failure recovery by reconciling from Postgres durable state."""
    logger.info("Running Redis failure reconciliation drill...")
    async for session in get_db():
        summary = await reconcile_after_redis_loss(db_session=session, redis_client=redis_client)
        logger.info("Redis reconciliation drill complete: %s", summary)
        break


def main() -> None:
    parser = argparse.ArgumentParser(description="Hadron Disaster Recovery & Verification Drill")
    parser.add_argument(
        "--action",
        choices=["backup", "restore-drill", "test-redis-reconcile"],
        required=True,
        help="Action to execute",
    )
    parser.add_argument("--out", type=str, default=None, help="Output file path for backup snapshot")
    parser.add_argument("--snapshot", type=str, default=None, help="Input snapshot path for restore drill")

    args = parser.parse_args()

    if args.action == "backup":
        asyncio.run(run_backup(args.out))
    elif args.action == "restore-drill":
        if not args.snapshot:
            logger.error("--snapshot argument is required for restore-drill")
            sys.exit(1)
        asyncio.run(run_restore_drill(args.snapshot))
    elif args.action == "test-redis-reconcile":
        asyncio.run(run_redis_reconcile_drill())


if __name__ == "__main__":
    main()
