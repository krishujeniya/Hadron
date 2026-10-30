# backend/disaster_recovery/tombstones.py
#
# Persistent Tombstone Ledger for GDPR Art. 17 / CCPA Right to Erasure obligations.
# Ensures that restoring an earlier database backup does NOT resurrect deleted customer data.

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.disaster_recovery.crypto import compute_sha256

logger = logging.getLogger(__name__)

_DEFAULT_TOMBSTONE_PATH = Path("docs/tombstones/erasure_tombstones.jsonl")


def record_tombstone(
    tenant_id: str,
    actor: str,
    reason: str = "Right to Erasure (GDPR Art. 17 / CCPA)",
    timestamp: datetime | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """
    Appends an immutable tombstone record for an erased tenant.
    """
    ledger_path = path or _DEFAULT_TOMBSTONE_PATH
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    ts = (timestamp or datetime.now(timezone.utc)).isoformat()
    record = {
        "tenant_id": tenant_id,
        "action": "tenant_erased_tombstone",
        "actor": actor,
        "reason": reason,
        "timestamp": ts,
    }
    record["integrity_hash"] = compute_sha256(json.dumps(record, sort_keys=True))

    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    logger.info("Recorded erasure tombstone | tenant=%s actor=%s timestamp=%s",
                tenant_id, actor, ts)
    return record


def get_tombstones(
    since: datetime | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Returns all tombstones recorded in the ledger, optionally filtered by timestamp >= since.
    """
    ledger_path = path or _DEFAULT_TOMBSTONE_PATH
    if not ledger_path.exists():
        return []

    tombstones = []
    try:
        lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            if not line.strip():
                continue
            entry = json.loads(line)
            if since:
                entry_dt = datetime.fromisoformat(entry["timestamp"])
                if entry_dt < since:
                    continue
            tombstones.append(entry)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error reading tombstone ledger at %s: %s", ledger_path, exc)

    return tombstones
