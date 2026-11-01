# Runbook: RB-05 Budget Ledger Reconciliation & Outage Recovery

## 1. Trigger & Symptom
- Discrepancy between Redis daily spend key (`hadron:budget:<date>:<tenant>`) and PostgreSQL settled ledger (`llm_call_log`).
- Alert: `budget_reconciliation_drift_exceeded` or economics page displays warning banner.

## 2. Diagnosis Steps
1. Query total settled spend from PostgreSQL for the target date:
   ```sql
   SELECT COALESCE(SUM(cost_usd), 0.0) as settled_usd, COUNT(*) as call_count
   FROM llm_call_log
   WHERE created_at >= CURRENT_DATE
     AND (tenant_id = '<tenant_id>' OR '<tenant_id>' IS NULL);
   ```
2. Read the running total cached in Redis:
   ```bash
   redis-cli -u $REDIS_URL GET "hadron:budget:$(date +%Y-%m-%d):<tenant_id>"
   ```
3. Calculate the delta (`settled_usd - redis_usd`).

## 3. Remediation Procedure
1. Re-sync Redis with PostgreSQL authoritative spend:
   ```bash
   python -m backend.economics.budget --sync-ledger --date $(date +%Y-%m-%d)
   ```
2. If Redis was restarted without persistence, the sync script recalculates running spend from `llm_call_log` and sets appropriate key TTLs (86,400s).
3. Verify that the economics dashboard `/economics` reflects settled numbers with green reconciled indicator.
