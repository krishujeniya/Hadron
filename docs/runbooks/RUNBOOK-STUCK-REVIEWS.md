# Runbook: RB-01 Stuck Reviews Recovery

## 1. Trigger & Symptom
- Review record remains in `reviewing` or `queued` status for > 15 minutes.
- Metric alert: `pr_review_stalled_duration_seconds > 900`.

## 2. Diagnosis Steps
1. Query database for stalled reviews:
   ```sql
   SELECT id, repo_full_name, pr_number, status, created_at, updated_at
   FROM pr_review_records
   WHERE status IN ('queued', 'reviewing')
     AND updated_at < NOW() - INTERVAL '15 minutes';
   ```
2. Check Redis ARQ queue depth and active worker processes:
   ```bash
   redis-cli -u $REDIS_URL LLEN arq:queue
   ```
3. Check worker container logs for out-of-memory (OOM) or unhandled worker crashes:
   ```bash
   docker logs hadron-worker --tail 100
   ```

## 3. Remediation Procedure
1. If the worker crashed, restart the worker container:
   ```bash
   docker compose restart worker
   ```
2. For orphaned review records whose worker terminated prematurely, execute the reconciliation script:
   ```bash
   python -m backend.disaster_recovery.reconciliation --timeout-minutes 15
   ```
3. Verify that the stalled review transitioned to `failed` or was re-enqueued with updated timestamp.
4. Notify affected user if ticket was raised.
