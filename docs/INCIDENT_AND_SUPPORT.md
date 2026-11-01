# Hadron Incident Response, Support Escalation & Privacy-Aware Telemetry

This document defines the operational support model, incident severity classification, escalation rosters, diagnostic protocols, tabletop exercises, and privacy-preserving product measurement for Hadron.

---

## 1. Incident Severity Tiers & Ownership

| Severity | Definition | Response SLA | Primary Owner | Escalation Path |
| :--- | :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Core review pipeline stalled, widespread webhook drops (>1% over 1h), unauthorized data access suspected, or database offline. | **≤ 15 minutes** | SRE Incident Commander (`sre-oncall@hadron.dev`) | VP Engineering & Security Lead |
| **SEV-2 (Major)** | Upstream LLM provider degraded with circuit breakers active, queue delay > 60s, or publication outbox backlog accumulating. | **≤ 30 minutes** | Backend On-Call Engineer | SRE Lead |
| **SEV-3 (Moderate)** | Single-tenant rate limit or isolated budget warning, transient dashboard read degradation, or minor UI rendering bug. | **≤ 4 hours** | Product Operations | Backend Engineering Team |
| **SEV-4 (Low)** | User feedback on a false-positive finding, cosmetic UI imperfection, or documentation typo. | **≤ 24 hours** | Customer Support | Assigned Milestone Maintainer |

---

## 2. Operational Runbooks Index

| Runbook ID | Title | Summary & Trigger | Document Link |
| :--- | :--- | :--- | :--- |
| **RB-01** | **Stuck Reviews Recovery** | Resolves reviews stuck in `reviewing` or `queued` state due to worker restart or unhandled exceptions. | [`RUNBOOK-STUCK-REVIEWS.md`](file:///home/ai/Documents/projects/Freelance/Hadron/docs/runbooks/RUNBOOK-STUCK-REVIEWS.md) |
| **RB-02** | **Provider Outage & Fallback** | Handles upstream LLM (OpenAI/Anthropic) latency spikes, 5xx outages, and rate limit exhaustion. | [`RUNBOOK-PROVIDER-OUTAGE.md`](file:///home/ai/Documents/projects/Freelance/Hadron/docs/runbooks/RUNBOOK-PROVIDER-OUTAGE.md) |
| **RB-03** | **Wrong Finding & Dispute** | Handles developer reports of false-positive or misleading recommendations with feedback logging. | [`RUNBOOK-BAD-RECOMMENDATION.md`](file:///home/ai/Documents/projects/Freelance/Hadron/docs/runbooks/RUNBOOK-BAD-RECOMMENDATION.md) |
| **RB-04** | **Unauthorized Access Containment** | Immediate isolation, session invalidation, and credential rotation upon unauthorized cross-tenant attempt. | [`RUNBOOK-UNAUTHORIZED-ACCESS.md`](file:///home/ai/Documents/projects/Freelance/Hadron/docs/runbooks/RUNBOOK-UNAUTHORIZED-ACCESS.md) |
| **RB-05** | **Budget Ledger Reconciliation** | Recovery and reconciliation when Redis running totals or Postgres cost ledger are out of sync. | [`RUNBOOK-BUDGET-LEDGER-OUTAGE.md`](file:///home/ai/Documents/projects/Freelance/Hadron/docs/runbooks/RUNBOOK-BUDGET-LEDGER-OUTAGE.md) |
| **RB-06** | **Failed Publication Reconciliation** | Re-delivers reviews to GitHub following upstream GitHub timeouts without duplicate comments. | [`RUNBOOK-FAILED-PUBLICATION.md`](file:///home/ai/Documents/projects/Freelance/Hadron/docs/runbooks/RUNBOOK-FAILED-PUBLICATION.md) |

---

## 3. Privacy-Aware Telemetry & Measurement Contract

Hadron collects operational telemetry to monitor system health and review usefulness while strictly preserving code confidentiality and regulatory privacy (GDPR / CCPA):

### What is Measured:
1. **Durable Review Completion:** Anonymized review UUID, timestamp, execution duration, and terminal status (`completed`, `failed`, `escalated`).
2. **Review Utility Signals:** User interactions on findings (expanded, dismissed, copied suggested change) aggregated as counts.
3. **Task Error Rates:** System error codes (HTTP 4xx/5xx) and worker exception classes paired with request trace IDs.
4. **Token & Dollar Accounting:** Consumed prompt/completion tokens and calculated cost per PR for budget enforcement.

### Strictly Prohibited From Telemetry:
- ❌ Customer repository source code, diff hunks, or file contents.
- ❌ GitHub personal access tokens, OAuth cookies, or installation private keys.
- ❌ Full review comment bodies or PR titles containing customer intellectual property.
- ❌ Raw stack traces containing internal file system paths exposed to client browsers.

---

## 4. Synthetic Tabletop Incident Protocol

Every release candidate undergoes a tabletop incident simulation covering:
1. **Scenario Injection:** Simulate upstream provider 503 outage during an active batch of 20 concurrent reviews.
2. **Detection & Triage:** Verify automated alert triggers within 5 minutes and points directly to `RB-02`.
3. **Mitigation:** Switch model routing to fallback tier; ensure running jobs transition to `escalated` or graceful retry rather than silent drop.
4. **Post-Mortem & Evidence:** Record incident timeline, impact window, root cause, and verify customer audit ledger remains consistent.
