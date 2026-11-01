#!/usr/bin/env python3
"""
scripts/preflight_check.py

Operational Preflight & Canary Gate CLI.
Executes release checks before traffic promotion in CI/CD or deployment pipelines.

Usage:
  python3 scripts/preflight_check.py --env staging
  python3 scripts/preflight_check.py --env production --approver "SRE-Lead" --artifact "sha256:abc123"
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import get_settings
from backend.rollout.preflight import (
    create_release_manifest,
    run_canary_health_check,
    run_migration_preflight,
    verify_environment_separation,
)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Hadron Release Preflight and Canary Health Check")
    parser.add_argument("--env", default="production", choices=["development", "staging", "production", "test"],
                        help="Target deployment environment")
    parser.add_argument("--approver", default="Release-Owner", help="Name of release approver")
    parser.add_argument("--artifact", default="unspecified-artifact-digest", help="Container image or commit digest")
    parser.add_argument("--rollback-target", default="previous-git-sha", help="Target artifact for automated rollback")
    parser.add_argument("--skip-canary", action="store_true", help="Skip runtime canary health check")
    args = parser.parse_args()

    cfg = get_settings()
    print("\n========================================================")
    print(f"HADRON RELEASE PREFLIGHT CHECK — ENV: {args.env.upper()}")
    print("========================================================\n")

    overall_passed = True

    # Check 1: Environment Separation
    print("[1/3] Checking environment separation and secrets...")
    env_report = verify_environment_separation(args.env, cfg)
    for c in env_report.checks:
        status = "✓ PASS" if c.passed else "✗ FAIL"
        print(f"  {status} [{c.check_name}]: {c.details}")
    if not env_report.passed:
        overall_passed = False
        print("  --> FAILED: Environment separation checks violated.")

    # Check 2: Database Migration Preflight
    print("\n[2/3] Checking database schema readiness and migration status...")
    mig_report = await run_migration_preflight(cfg)
    for c in mig_report.checks:
        status = "✓ PASS" if c.passed else "✗ FAIL"
        print(f"  {status} [{c.check_name}]: {c.details}")
    if not mig_report.passed:
        overall_passed = False
        print("  --> FAILED: Database schema migration preflight failed.")

    # Check 3: Canary Health Probe
    if not args.skip_canary:
        print("\n[3/3] Checking canary health and orchestrator engine wiring...")
        canary_report = await run_canary_health_check(cfg)
        for c in canary_report.checks:
            status = "✓ PASS" if c.passed else "✗ FAIL"
            print(f"  {status} [{c.check_name}]: {c.details}")
        if not canary_report.passed:
            overall_passed = False
            print("  --> FAILED: Canary health checks failed.")
    else:
        print("\n[3/3] Canary health check skipped by flag.")

    # Final verdict & Release Manifest creation
    print("\n--------------------------------------------------------")
    if overall_passed:
        manifest = create_release_manifest(
            approver=args.approver,
            artifact_digest=args.artifact,
            rollback_target=args.rollback_target,
            environment=args.env,
            cfg=cfg,
        )
        print("PREFLIGHT STATUS: APPROVED FOR PROMOTION")
        print("Release Manifest generated:")
        print(json.dumps(manifest.to_dict(), indent=2))
        return 0
    else:
        print("PREFLIGHT STATUS: REJECTED — RESOLVE BLOCKERS BEFORE PROMOTING TRAFFIC")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
