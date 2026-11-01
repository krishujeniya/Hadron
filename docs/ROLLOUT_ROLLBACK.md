# Hadron Safe Rollout, Rollback, and Operational Feature Controls (T26)

This document establishes the canonical operational procedures for deploying, validating, feature-flagging, and rolling back releases of the Hadron PR Review Agent.

---

## 1. Environment Separation and Isolation

Hadron enforces strict boundary isolation across deployment tiers:

| Environment | Purpose | Database | GitHub App Installation | Secrets & Keys |
|---|---|---|---|---|
| **Development** | Local developer testing | Local Postgres (`hadron_dev`) | Sandbox GitHub App | Mock / test keys allowed |
| **Staging** | Automated pre-promotion validation | Isolated Staging RDS (`hadron_staging`) | Dedicated Staging GitHub App | Real provider test quotas, isolated from Prod |
| **Production** | Live PR review execution | Production RDS (`hadron_prod`) with SSL | Production Verified GitHub App | Rotated production secrets, strictly no test keys |

### Enforced Rules
1. **No Shared Credentials:** A production secret (OpenAI API key, GitHub webhook secret, JWT secret, DB password) must never be shared with development or staging.
2. **Database TLS:** Production PostgreSQL connections require TLS with hostname and certificate verification enabled (`POSTGRES_SSL=True`).
3. **Automated Guard:** `backend/rollout/preflight.py:verify_environment_separation()` rejects deployments if default placeholders (e.g. `change-me-in-production`, `sk-placeholder`) are detected in production configurations.

---

## 2. Release Sequence & Promotion Gates

Every release follows an immutable artifact pipeline:

```
[Git Commit]
      │
      ▼
1. Build Immutable Image (sha256 digest tagged)
      │
      ▼
2. Staging Deployment & Migration Preflight (`scripts/preflight_check.py --env staging`)
      │
      ▼
3. Canary Deployment (10% traffic route)
   - Worker heartbeat verified
   - Synthetic in-memory dry-run passes
      │
      ▼
4. Traffic Promotion (50% → 100%)
   - Automated release manifest recorded with approver signature
```

---

## 3. Operational Kill Switches

Hadron provides three independent, immediate kill switches configured via environment variables or runtime settings:

### A. Publication Kill Switch (`KILL_SWITCH_PUBLICATION=true`)
- **Action:** Halts posting reviews and comments to GitHub (`backend/orchestrator/nodes.py:post_review`).
- **Behavior:** Local agent analysis and review computation continue normally. Computed review findings are saved to PostgreSQL with status `held_by_kill_switch`.
- **Use Case:** Upstream GitHub API rate limits, temporary spam review mitigation, or review quality audit without losing pending queue progress.

### B. New Intake Kill Switch (`KILL_SWITCH_NEW_INTAKE=true`)
- **Action:** Rejects incoming webhook reviews at the enqueue boundary (`backend/job_queue/arq_worker.py:enqueue_review_job`) with HTTP 503 and `Retry-After: 60`.
- **Behavior:** In-flight accepted review jobs continue to completion. Allows the queue to cleanly drain.
- **Use Case:** Routine worker maintenance, database migration, or downstream queue drain.

### C. Provider Spend Kill Switch (`KILL_SWITCH_PROVIDER_SPEND=true`)
- **Action:** Immediately blocks all paid LLM calls (`backend/tools/llm_client.py:call_openai, call_anthropic`) and vector embedding requests (`backend/memory/embedder.py`).
- **Behavior:** Raises `ProviderSpendHaltedError` / `EmbeddingError`. Prevents any outbound token charges.
- **Use Case:** Unexpected runaway cost anomaly, credit quota exhaustion, or compromised provider API key.

---

## 4. Feature Flags & Canary Model Routing

1. **RAG Context Flag (`ENABLE_RAG_CONTEXT=false`):**
   - When set to `false`, RAG retrieval is cleanly bypassed in `build_context`, returning empty context without degrading review pipeline reliability.
2. **Canary Models Flag (`ENABLE_CANARY_MODELS=true`, `CANARY_MODEL=o1-mini`):**
   - Routes quality review agent traffic to experimental reasoning models for canary testing before site-wide rollout.

---

## 5. Rollback vs. Forward Migration Repair

### Rollback Strategy
When a bad release is detected post-deployment:
1. **Frontend / API Rollback:**
   - Immediately redeploy the prior immutable container image digest referenced in the active `ReleaseManifest.rollback_target`.
2. **Drain Intake:**
   - Enable `KILL_SWITCH_NEW_INTAKE=true` if database schema compatibility is uncertain.
3. **Zero-Downtime Schema Policy:**
   - Database migrations must strictly follow the **Expand / Contract** pattern.
   - Column additions must be nullable or have safe defaults.
   - Dropping old columns/tables is prohibited during the active version deployment. Old and new code versions can safely run concurrently against the database.

### Forward Migration Repair
If a migration was applied with an unexpected constraint or logic error:
1. Do **NOT** run destructive manual `DROP TABLE` or `ROLLBACK` commands on production.
2. Write a new timestamped migration script in `scripts/migrations/` fixing the constraint or column definition.
3. Apply via the standard migration runner (`backend/database/postgres.py:init_tiger_schema`).

---

## 6. Secret Rotation & Token Revocation Runbook

### Emergency Procedure: Compromised GitHub App / Webhook Secret
1. Generate new GitHub App client secret / webhook secret in GitHub Settings.
2. Update deployment secret manager (e.g. AWS Secrets Manager, Railway/Kubernetes secrets).
3. Restart API instances (`docker-compose restart api` or rolling restart).
4. Revoke old compromised secret in GitHub App settings.
5. Verify `/webhook/github` receives and validates signed payloads with the new secret.

### Emergency Procedure: Compromised Provider API Key (OpenAI / Anthropic)
1. Enable `KILL_SWITCH_PROVIDER_SPEND=true` to immediately stop any unauthorized usage.
2. Issue replacement key in provider dashboard and update secret environment variable.
3. Rotate and redeploy.
4. Disable `KILL_SWITCH_PROVIDER_SPEND=false`.
5. Revoke compromised key in provider dashboard.
