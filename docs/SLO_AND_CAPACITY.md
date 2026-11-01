# Hadron Service Level Objectives (SLOs) & Capacity Specifications

This document defines the formal Service Level Indicators (SLIs), Service Level Objectives (SLOs), error budget policies, and capacity management benchmarks for Hadron in accordance with Google SRE error budget practices [S17].

---

## 1. Core Service Level Indicators (SLIs)

| SLI ID | Indicator Name | Specification (Numerator / Denominator) | Measurement Window | Target (SLO) | Exclusions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SLI-1** | **Webhook Durable Receipt** | Valid GitHub webhook events persisted to PostgreSQL and acknowledged with HTTP 200/202 within 10.0 seconds / Total valid incoming webhook events. | Rolling 28 days | **99.9%** | Events with invalid HMAC-SHA256 signatures, malformed JSON, or untracked GitHub event types. |
| **SLI-2** | **Worker Fleet Queue Delay** | Time elapsed between job enqueue and worker pickup / Total enqueued review jobs. | Rolling 7 days | **p95 ≤ 30s** | Scheduled downtime, non-critical cron jobs. |
| **SLI-3A** | **Small PR Review Latency** | Time from worker start to completed aggregation for PRs with ≤ 10 files and ≤ 500 lines of diff. | Rolling 7 days | **p95 ≤ 120s** | Reviews blocked waiting for human-in-the-loop (HITL) governance decisions. |
| **SLI-3B** | **Medium PR Review Latency** | Time from worker start to completed aggregation for PRs with ≤ 50 files and ≤ 2,000 lines of diff. | Rolling 7 days | **p95 ≤ 300s** | Reviews blocked waiting for HITL governance decisions. |
| **SLI-4** | **Review Publication Outbox** | Completed reviews successfully delivered to GitHub or reconciled via outbox within 15.0s / Total terminal completed reviews. | Rolling 28 days | **99.5%** | Upstream GitHub REST API rate limits (HTTP 429) or upstream GitHub outages. |
| **SLI-5** | **Dashboard API Read Latency** | Authenticated workspace list and detail requests (`/api/v1/reviews`, `/api/v1/hitl`, `/api/v1/economics`) responding in ≤ 500ms / Total authenticated GET requests. | Rolling 7 days | **p95 ≤ 500ms** | Client-side mobile network latency; slow consumer aborts. |

---

## 2. Noisy Neighbor Protection & Capacity Boundaries

Hadron enforces strict multi-tenant capacity isolation to protect against tenant starvation and noisy-neighbor workloads:

1. **Per-Tenant Concurrency Caps:**
   - Maximum active concurrent review jobs per workspace: `10` concurrent PR workflows.
   - Additional PRs from the same repository or tenant are held in Redis priority queue sorted by commit arrival timestamp.
2. **LLM Provider Circuit Breaker:**
   - Token bucket per tenant: Max 150,000 tokens/minute.
   - Dynamic degradation to fast-tier model when budget warning threshold (80%) is exceeded.
3. **Database Connection Pool Partitioning:**
   - API fleet pool: 20 connections max.
   - Worker fleet pool: 30 connections max.
   - Dedicated connection slots reserved for health monitoring and disaster recovery drills.

---

## 3. Error Budget & Burn-Rate Alerting Policy

Error budget is calculated as:
$$\text{Error Budget} = 100\% - \text{SLO Target}$$

For SLI-1 (99.9% target over 28 days), the error budget is **0.1%** (approx. 40.3 minutes of unmitigated outage per 28-day cycle).

### Multi-Window Multi-Burn-Rate Alerts:
1. **Critical Page (Severity 1):**
   - **Condition:** 14.4x burn rate over 1 hour (2% of monthly budget consumed in 1h) OR 6x burn rate over 6 hours (5% of budget consumed in 6h).
   - **Action:** Automated pager notification to on-call SRE; trigger upstream provider fallback; engage disaster recovery runbook.
2. **Warning Ticket (Severity 2):**
   - **Condition:** 3x burn rate over 24 hours (10% of monthly budget consumed in 24h).
   - **Action:** Automated JIRA/Linear ticket to backend engineering; investigate slow queries or agent provider latency spikes.
3. **Release Freeze Rule:**
   - If remaining error budget over the trailing 28 days drops below **10%**, all non-critical feature deployments are frozen until error budget recovers.

---

## 4. Runbook Mapping

| Alert / Symptom | Primary SLI Violated | Immediate Remediation Runbook |
| :--- | :--- | :--- |
| Webhook timeout > 10s | SLI-1 | `docs/runbooks/RUNBOOK-WEBHOOK-STALL.md` |
| Queue buildup / depth > 50 | SLI-2 | `docs/runbooks/RUNBOOK-WORKER-SCALING.md` |
| Agent review execution timeout | SLI-3 | `docs/runbooks/RUNBOOK-AGENT-CIRCUIT-BREAKER.md` |
| GitHub publication delivery failure | SLI-4 | `docs/runbooks/RUNBOOK-OUTBOX-RECONCILIATION.md` |
| Dashboard API p95 > 500ms | SLI-5 | `docs/runbooks/RUNBOOK-DATABASE-QUERY-PERFORMANCE.md` |
