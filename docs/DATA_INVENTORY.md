# Hadron Data Inventory & Governance Policy

This document establishes the official data inventory, classification, retention lifecycle, deletion paths, and third-party data processor policies for the Hadron Autonomous AI PR Review Agent.

---

## 1. System Overview & Data Lifecycle

Hadron processes pull requests from GitHub repositories, analyzes diffs using specialized AI agents, and publishes actionable code review comments. To satisfy enterprise privacy commitments, SOC 2 compliance, GDPR Article 17/20, and CCPA requirements, Hadron adheres to the following core tenets:

1. **Principle of Least Privilege**: Sensitive credentials (such as GitHub installation tokens) are never persisted to disk or databases; they reside strictly in ephemeral memory with short TTLs.
2. **Separation of Audit Integrity from Raw Code**: Review verdicts, high-level metrics, and finding summaries are retained for compliance, while raw code diffs and sensitive snippets are automatically scrubbed after their active review lifecycle.
3. **Tenant-Scoped Isolation**: All persisted data is scoped by `tenant_id` (`owner` or `owner/repo`). Deletion and export requests operate strictly within tenant boundaries.
4. **Legal-Hold Protection**: Active legal holds freeze automated purges and deletion operations until formally released by an authorized compliance officer.

---

## 2. Comprehensive Data Element Inventory

| Data Category | Data Element | Purpose | Storage Store & Table | Access Level | Default Retention | Deletion & Purge Path | Legal-Hold Handling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Source Code & Diffs** | PR Diff & Patch text | Agent security & quality analysis | PostgreSQL `pr_review_records.diff` | Internal Workers | 14 days (raw diff scrubbed) | Automated scheduled scrub; `DELETE` on tenant offboarding | Hold freezes scrub |
| **Source Code & Diffs** | File Paths & Line Ranges | Finding attribution & display | PostgreSQL `finding_records` | Reviewer, Admin | 90 days with review | `CASCADE` on review deletion | Hold freezes purge |
| **Review Records** | Verdict, Status, Confidence | PR review results & pipeline health | PostgreSQL `pr_review_records` | Viewer, Reviewer, Admin | 90 days | Tenant purge API / GitHub uninstall | Hold freezes purge |
| **Review Findings** | Summary, Suggestion, Category | Developer feedback & remediation | PostgreSQL `finding_records` | Reviewer, Admin | 90 days | `CASCADE` on review deletion | Hold freezes purge |
| **Vector Embeddings** | Code chunks & embedding vectors | Semantic RAG context for reviews | TimescaleDB / pgvector `code_chunks` | Internal Workers | Until repo or tenant deleted | `DELETE FROM code_chunks WHERE repo_full_name LIKE 'tenant/%'` | Hold freezes drop |
| **Financial Ledger** | Model tokens, cost in USD | Daily budget caps & LLM accounting | PostgreSQL `cost_ledger`, `llm_call_logs` | Admin | 365 days (financial audit) | Anonymized on tenant offboarding | Preserved for financial audit |
| **Telemetry & Events** | Agent execution events, latency | Pipeline observability & tracing | TimescaleDB `agent_events`, JSONL | Admin | 90 days | Timescale drop chunk / JSONL roll | Preserved for compliance |
| **User Sessions** | Session token, GitHub OAuth state | Web UI authentication & RBAC | Redis `session:{token}` | Authenticated Principal | 7 days TTL | Key expiration or explicit logout | Revoked immediately |
| **Human-in-the-Loop** | HITL disputes & decision logs | Escalation review & governance | PostgreSQL `hitl_reviews`, `hitl_feedbacks` | Reviewer, Admin | 180 days | Tenant deletion API | Hold freezes purge |
| **Credentials** | Webhook secrets, GitHub App keys | External GitHub integration | Ephemeral memory / environment | Service configuration | Ephemeral (zero DB storage) | Unset environment variable | N/A |

---

## 3. Third-Party LLM Processor Retention & Privacy Policies

Hadron dispatches prompt payloads to approved LLM providers. All provider integrations are configured with strict data-use opt-outs:

1. **OpenAI**: Configured under Commercial API terms with Zero Data Retention (ZDR) where eligible; OpenAI does not use customer API inputs or outputs to train OpenAI models.
2. **Anthropic**: Commercial API payloads are not used for model training; logs are retained only for security analysis up to 30 days before permanent deletion.
3. **NVIDIA NIM**: Self-hosted or enterprise-dedicated NIM container endpoints do not log or store inference inputs outside the customer environment.

---

## 4. Retention & Scheduled Purge Lifecycle

Hadron enforces automated data scrubbing via `backend.governance.retention`:

- **Raw Code Scrub (14 Days)**: To prevent unbounded storage of private proprietary source code, `diff` columns in `pr_review_records` are cleared (`NULL`) 14 days after review completion. Findings, line numbers, and confidence metrics remain intact for reporting.
- **Review Expiry (90 Days)**: PR reviews and associated findings older than 90 days are purged unless flagged for retention or protected by an active legal hold.
- **Idempotency & Replay Safety**: All purge operations run in batches, use monotonic timestamp predicates, and are fully idempotent. Failed purge steps can be safely retried without risk of inconsistent state.

---

## 5. Tenant Data Deletion & Offboarding (Right to Erasure)

When a tenant offboards or uninstalls the Hadron GitHub App (`installation.deleted` webhook event):
1. **Legal Hold Check**: If `legal_holds` is active for the tenant, deletion is rejected with `HTTP 409 Conflict`.
2. **Relational Cascade**: All rows in `pr_review_records`, `finding_records`, `repo_file_index_records`, `hitl_reviews`, `hitl_feedbacks`, and `llm_call_logs` matching the tenant prefix are deleted.
3. **Vector Namespace Cleanse**: All vector chunks in `code_chunks` associated with the tenant's repositories are removed from pgvector.
4. **Cache & State Flush**: Redis keys corresponding to the tenant (`tenant_active:{tenant}`, `review:status:*`, `dlq:*`) are evicted.
5. **Audit Proof**: An immutable audit event is recorded documenting the date, requesting actor, and record counts deleted, maintaining audit compliance without retaining private source code.

---

## 6. Scoped Data Export (Portability)

Tenants can request a machine-readable archive of all data associated with their organization:
- **Endpoint**: `POST /api/v1/governance/export`
- **Authentication**: Requires Tenant Admin role or global Admin API key.
- **Format**: Structured JSON containing all PR review records, findings, HITL decisions, and ledger spend summaries.
- **Security**: Exports exclude internal system secrets and other tenants' data. Signed export manifests expire after 24 hours. Rate limited to 5 requests per tenant per 24-hour period.

---

## 7. Legal-Hold Framework

Legal holds allow authorized compliance personnel to freeze automated data deletion:
- `POST /api/v1/governance/tenants/{tenant_id}/legal-hold`: Places an active hold with documented legal justification.
- `DELETE /api/v1/governance/tenants/{tenant_id}/legal-hold`: Releases the hold.
- Any purge or tenant deletion targeting a tenant under legal hold fails with an explicit `LegalHoldActiveError`.
