"""
backend/rollout

Release controls, preflight validation, feature toggles, and operational kill switches.
"""

from backend.rollout.preflight import (
    PreflightCheckResult,
    PreflightReport,
    ReleaseManifest,
    compute_prompt_hashes,
    create_release_manifest,
    run_canary_health_check,
    run_migration_preflight,
    verify_environment_separation,
)

__all__ = [
    "PreflightCheckResult",
    "PreflightReport",
    "ReleaseManifest",
    "compute_prompt_hashes",
    "create_release_manifest",
    "run_canary_health_check",
    "run_migration_preflight",
    "verify_environment_separation",
]
