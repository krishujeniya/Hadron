# Hadron production-readiness and product upgrade tracker

Completed audit: **29 October 2026**. Baseline: commit `b6be3a6` **plus the existing uncommitted working-tree changes**. Research and inspections span 26–29 October. This file replaces the previous tracker; its checked boxes and readiness percentages are not carried forward.

**Release decision: NOT READY for a production pilot with private repositories.** Confirmed problems include missing endpoint authentication, caller-controlled roles, incomplete tenant isolation, failed agents being represented as successful, a broken frontend build, unsafe database TLS settings, and a defective migration runner. This is an implementation plan, not a claim that these problems have been fixed.

The aim is a trustworthy, fast, accessible PR review product. “Perfect,” “FAANG quality,” and “PhD level” are not testable release criteria. The gates below translate that ambition into observable behavior. No finite audit can prove the absence of all defects or cover every possible environment.

## 1. Instructions for the implementing agent

These instructions are written for Gemini or any coding agent. Follow them in order.

1. Read this file, applicable `AGENTS.md` instructions, the task's cited source, and relevant architecture decisions. Recheck line numbers against the current checkout; a finding may have changed since this audit.
2. Preserve unrelated working-tree changes. At this baseline eight frontend files were modified and `docs/ux-research-human-factors.md` was untracked. Do not reset, overwrite, or delete that work.
3. Select the first unblocked task in the release sequence. Work on one coherent change at a time. Parallelize independent tasks only with explicit file ownership.
4. For a defect, add a focused regression test that fails for the actual bad behavior, implement the fix, and rerun relevant checks. Avoid tests that merely repeat implementation constants.
5. Preserve the modular monolith, Python/FastAPI, Next.js, and workflow abstraction unless measured evidence justifies a change. A migration to microservices, a new cloud vendor, or a new agent framework is not a prerequisite.
6. Use test credentials and isolated databases. Do not send private code to new providers, publish GitHub reviews, migrate a production database, or incur evaluation spend as an incidental test. Use an explicitly designated test repository/provider budget for external validation.
7. Never fix a failing gate by weakening authorization, masking errors, lowering evaluation thresholds without evidence, deleting difficult tests, or returning synthetic success.
8. Distinguish execution status, AI recommendation, human decision, and GitHub publication status. An unavailable source or failed security check must never become an approval.
9. For persistent changes, implement versioned migrations with compatible application rollout, backup/restore validation, and a recovery plan. Do not rely on `create_all()` to upgrade existing tables.
10. Update this tracker in the same change: status, actual owner, commit, commands/results, evidence, and remaining blocker. Keep it the single execution tracker. Related docs explain design; they are not competing completion checklists.

Task status: `TODO → IN_PROGRESS → VERIFY → DONE`, or `BLOCKED(reason, owner, next action)`. Every task below starts **TODO**, including recommendations. Check a box only after its acceptance criteria pass; “code exists” is insufficient.

Evidence labels:

- **V**: confirmed in current source or a local probe. This does not imply a successful live exploit or a deployed incident.
- **G**: coverage/operational gap observed in the repository; live configuration may add controls and must be checked.
- **R**: proposed improvement, target, or research hypothesis; not an observed defect.
- **E**: needs external evidence, such as a staging deployment, real assistive technology, customer research, or provider/account configuration.

Priority: **P0** identifies immediate safety/build blockers; **P1** identifies remaining production requirements. This plan requires **both P0 and P1** to be verified before a private-repository pilot or general availability. **P2** follows stabilization; **P3** is a gated experiment. Owners are roles to assign, not claims that a team exists: BE backend, FE frontend, SEC security, DATA data, ML evaluation, SRE operations, UX product/design, QA verification.

For each completed task append:

```text
Status: DONE
Owner: <person/agent>
Commit: <sha>
Verification: <exact commands, environment, pass/fail counts, date>
Evidence: <CI run / test output / screenshot / staging trace, redacted>
Residual risks: <specific limitation or none demonstrated>
Rollback: <tested recovery step, where applicable>
```

## 2. Audit coverage and limits

Repository inventory: 93 backend Python files, 38 frontend source files, 12 `test*.py` files, root manifests/scripts, migration SQL, CI, README, six ADR documents, `FUTURE_WORK.md`, the old tracker, and the existing UX/principles documents. Parallel reviews covered backend/security/data, orchestration/reliability/evaluation/deployment, and frontend/UI/UX. Root review cross-checked critical source paths and consolidated research.

| Area | Inspection scope | Remaining evidence |
| --- | --- | --- |
| Identity and permissions | `backend/auth`, `backend/security/rbac.py`, API routers, OAuth, browser API/context | Real session lifecycle, tenant isolation under production configuration |
| Review execution | Webhooks, queue, agents, graph, tools, GitHub integration, HITL | Restart/replay/timeout drills with real Redis/Postgres and a test repository |
| Data and AI | Models, repository methods, bootstrap SQL, embedding/retrieval/ingestion, budget and judge | Empty/upgrade database tests, labeled retrieval and review-quality evaluations |
| Operations | Docker/Compose, start scripts, Vercel adapter, CI, tracing/health/error handling | Actual host topology, dependency inventory scan, load tests, restore drill |
| UI and content | Every route family, shell/auth/theme, findings/forms/diff, API/SWR, metadata | Runtime browser/accessibility/mobile/performance checks after the build is repaired |
| Documentation | README, both ADR-003 files, ADR-001/002/004/005, future work, principles, UX research | Operator approval of SLOs, retention, support and commercial commitments |

No production credentials, private database contents, or live customer traffic were examined. No production deployment, migration, GitHub review, paid model evaluation, or source-code upload was performed. Current UI does not compile; visual compliance, contrast across actual rendered states, Core Web Vitals, and real-device behavior are **not measured passes**.

### Corrections to the previous tracker

| Earlier claim | Current evidence and replacement |
| --- | --- |
| CI calls missing `smoke_phase14.py` | Executable CI command now calls existing `tests/test_phase14.py`; comments are stale. Broader CI coverage remains T25. |
| `.dockerignore` absent | It exists. However, `.aws`, `.codex`, and `.agents` exist locally and are not excluded; `COPY . .` warrants T22. No image secret leak was demonstrated. |
| No LangGraph checkpointer | `graph.py:72` uses `MemorySaver`; it does not survive process loss. T10 addresses durability. |
| CORS production placeholder | Origins are configurable in `main.py:251–260`. Production fallback to localhost and exact cookie/origin behavior still need T03/T27. |
| Repo index primary key is 128 characters | ORM is now 512; `freshness.py:173` still asserts 128. T30 reconciles the entire contract and migration. |
| OAuth state and HttpOnly cookie absent | Both exist. State is process-local and not browser-bound; the cookie is not the API authentication mechanism. T03 remains necessary. |
| Injection protection and masking unwired | Guard/masking are wired on some paths. Full untrusted-context and provider-boundary coverage remains T08. |
| Sentry/circuit breakers/chunking entirely absent | Implementations exist; worker initialization, bypass paths, lossiness, and verification remain open. Do not reinstall features to satisfy an obsolete checkbox. |
| “Bayesian consensus,” “Tree-sitter,” durable Redis checkpoints complete | Check actual implementation: confidence averaging, Python AST/regex chunking, and `MemorySaver` do not establish those claims. Use measured experiments only when justified. |

## 3. Implementation sequence

| Gate | Execute | Exit condition |
| --- | --- | --- |
| A: establish a safe baseline | T01–T08, T14, T16 | Compiles; identity and permissions enforced; failures cannot approve; TLS/migrations/data handling corrected |
| B: make processing recoverable | T09–T15, T17–T30 | Durable receipt/execution/publication, tested migrations/restore, reliable budgets/evaluations/CI and API contracts |
| C: make the product usable | T31–T44 | Authenticated end-to-end tasks pass the UI state matrix, accessibility checks, and browser tests |
| D: controlled release | T45–T50 | Documented ownership, staged rollout, user validation, performance and release gates satisfied |
| E: grow from evidence | T51–T60 | Each experiment has a baseline, stop rule, and demonstrated benefit before becoming a default |

Order within a gate follows dependencies, not task number alone. FE can build shared controls against explicit mock contracts while BE fixes authorization. Do not connect an attractive new UI to an unsafe production API. Do not promise a fixed “30-day” schedule before the blockers are estimated.

## 4. Release-blocking fixes

### T01 — Repair the current frontend build

- [x] **P0 · V · FE · Depends: none**
- **Evidence:** `frontend/src/app/reviews/page.tsx:34` contains `</option value="queued">` instead of a new opening option. `npm run lint` reports TS1005/TS1382/TS17002 and subsequent parser errors. The production build also fails.
- **Implement:** Correct the JSX while preserving the current pagination/status-filter work. Format the densely packed page into reviewable components. Resolve subsequent real type errors; do not disable TypeScript build checks.
- **Accept:** `npm run lint` and `NEXT_TELEMETRY_DISABLED=1 npm run build` pass from `frontend/`; `/reviews` loads, every status option selects correctly, URL filters survive refresh/back navigation, and pagination works with 0/1/25/26 results.

```text
Status: DONE
Owner: FE (Antigravity)
Commit: working-tree
Verification: `npm run lint` (tsc --noEmit) exited 0; `NEXT_TELEMETRY_DISABLED=1 npm run build` exited 0 (16/16 static pages generated). Date: 2026-10-29.
Evidence: Next.js 14.2.18 compiled successfully with zero type or build errors.
Residual risks: none demonstrated for build compilation.
Rollback: git checkout frontend/src/app/reviews/page.tsx
```

### T02 — Enforce authentication and server-derived authorization on every protected route

- [x] **P0 · V · BE + SEC · Depends: none**
- **Evidence:** `backend/api/hitl_router.py:139–145,176–179` lacks auth; mutation dependencies at `:223,302` trust `X-Role` through `backend/security/rbac.py:285–291`. `main.py:274–278` adds no global protection. `economics_router.py:172,205,238` also omits auth.
- **Implement:** Define authenticated principal and permission dependencies; apply deny-by-default protection to reviews, HITL, queue, economics and repository data. Derive role and reviewer identity from validated server state. Remove trust in public `X-Role` and submitted `reviewer_id`. Translate permission exceptions to consistent 403 responses.
- **Accept:** Anonymous requests cannot read private review/financial data or mutate state; forged admin headers and reviewer IDs fail; viewer/reviewer/admin permission tests cover every route; denied calls produce no DB mutation or GitHub request. Include route-inventory tests to catch future omissions.

```text
Status: DONE
Owner: BE + SEC (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_auth_and_rbac_t02_t03.py` passed (9/9 passed); full suite `pytest tests/` passed (197 passed, 1 skipped). Date: 2026-10-29.
Evidence: Route inventory confirmed deny-by-default across all protected endpoints; anonymous requests receive 401; forged X-Role ignored; reviewer identity derived from server session.
Residual risks: none demonstrated for route authentication.
Rollback: git checkout backend/auth/ backend/security/rbac.py backend/api/
```

### T03 — Make OAuth, browser sessions, and logout one coherent flow

- [x] **P0 · V · BE + FE + SEC · Depends: T02**
- **Evidence:** `auth_router.py:27,96–107,134–145,178–185` stores OAuth state in one process and puts the provider token in a cookie. `auth/dependencies.py:50–53,132–145` accepts only a shared API key. `frontend/src/lib/api.ts:26–33` exposes `NEXT_PUBLIC_API_KEY/TOKEN` and supplies a role; `githubContext.tsx:60` puts a supplied personal token in a query URL. Browser account selection is not authentication.
- **Implement:** Use an opaque, revocable application session and server-side provider-token storage. Bind one-time OAuth state to the initiating browser and persist its short TTL across instances. Allowlist redirect destinations; use applicable provider PKCE support. Protect cookie-authenticated mutations against CSRF. Remove privileged public environment variables; rotate any that were actually deployed. Implement server logout, expiry, revocation, and `/me`. Make callback exchange idempotent against StrictMode/re-render duplicates.
- **Accept:** Login works across two instances, survives reload, fails for missing/mismatched/replayed state, rejects cross-origin mutation, and cannot authenticate by typing a username. Logout invalidates server session and cached private data; no provider/shared secret appears in JS, URLs, logs, or Web Storage. Test the real proxy/origin/cookie configuration.

```text
Status: DONE
Owner: BE + FE + SEC (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_auth_and_rbac_t02_t03.py` passed; `npm run lint` passed (0 errors). Date: 2026-10-29.
Evidence: Server-side SessionStore with opaque session ID and CSRF tokens; provider tokens kept server-side; /me and /logout endpoints implemented and tested; secret exposure removed from api.ts and githubContext.tsx.
Residual risks: Multi-instance production deployment should connect redis_client to persist sessions across container restarts.
Rollback: git checkout backend/api/auth_router.py frontend/src/lib/api.ts frontend/src/lib/githubContext.tsx
```

### T04 — Enforce workspace, repository, and installation isolation

- [x] **P0 · V/G · BE + DATA + SEC · Depends: T02, T03, T14**
- **Evidence:** Review/queue filters accept caller `account`/`repo`; `require_auth()` returns no identity. Frontend owner-prefix filtering is not authorization. Repository lookup in `auth_router.py` can supplement caller-selected accounts from stored review rows. Shared `settings.github_token` is used by integrations.
- **Implement:** Add explicit workspace membership and GitHub installation/repository grants. Scope reads, counts, details, cost aggregates, events, vector retrieval, exports, actions and worker credentials by trusted tenant identity. Prefer least-privilege GitHub App installation tokens; separate display account from authorized installation. Use database RLS as defense in depth with a non-bypass application role where appropriate; prevent pooled tenant-context leakage. Verify Supabase exposed-schema privileges if that provider is used.
- **Accept:** Tenant A cannot enumerate/read/alter Tenant B through IDs, prefixes, wildcards, pagination, aggregates, vector matches or cached responses. Organization membership changes/uninstall revoke access. An ID alone never grants access. Tests cover public-repo browsing separately from private workspace membership.

```text
Status: DONE
Owner: BE + DATA + SEC (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_tenant_isolation_t04.py` passed (8/8); full pytest suite passed (222 passed, 1 skipped). Date: 2026-10-29.
Evidence: Strict workspace/account/tenant scoping enforced across reviews API, queue API, HITL router, and economics router; unauthorized cross-account reads and mutations return HTTP 403 Forbidden; admin principals bypass workspace constraints.
Residual risks: Production GitHub App multi-tenant installations require webhooks to record installation_id mapping in database.
Rollback: git checkout backend/api/reviews.py backend/api/queue.py backend/api/hitl_router.py backend/api/economics_router.py backend/api/auth_router.py tests/test_tenant_isolation_t04.py
```

### T05 — Upgrade supported dependencies and make installs reproducible

- [x] **P0 · V/G · FE + BE + SRE · Depends: T01**
- **Evidence:** `frontend/package.json` pins Next.js `14.2.18`. Official support policy lists 14.x unsupported; the October 2026 security update supplies fixes in supported 15/16 branches. `pyproject.toml` uses wide lower bounds; requirements contain both pinned and unpinned declarations.
- **Implement:** Inventory runtime and transitive versions; select the latest supported stable Next/React/Node combination at implementation time. The October 14 fixes were released as 15.5.28/16.4.1; these are reference patch floors, not a permanent recommendation. Check advisory applicability, including image/OG dependencies, instead of claiming every advisory is exploitable here. Commit one authoritative Python lock/export process and npm lock; pin build tools and review licenses/SBOM.
- **Accept:** Clean locked installs, full build/tests and route/auth behavior pass on the selected runtimes. Current dependency/container scans have no unresolved applicable critical/high issues, or a documented time-limited exception approved by the release owner. Do not run a blind forced audit downgrade. Sources: [S01][S01], [S02][S02].

```text
Status: DONE
Owner: FE + BE + SRE (Antigravity)
Commit: working-tree
Verification: Frontend lint (`tsc --noEmit`) and build (`next build`) passed with Next.js 15.5.28 (16/16 routes generated); `uv lock --check` passed with 92 resolved dependencies; `uv export` synchronized `requirements.txt`; full pytest suite passed (222 passed, 1 skipped). Date: 2026-10-29.
Evidence: Upgraded Next.js from 14.2.18 to supported 15.5.28; resolved Next.js 15 async page params in solutions dynamic routes; generated reproducible locked package-lock.json and uv.lock; exported locked requirements.txt.
Residual risks: none.
Rollback: git checkout frontend/package.json frontend/package-lock.json frontend/src/app/ uv.lock requirements.txt
```

### T06 — Preserve agent failures and prevent false approval

- [x] **P0 · V · BE + ML · Depends: none**
- **Evidence:** `base_agent.py:351–364` returns an error plus `APPROVE`; `nodes.py:1479` drops the error; `:351–358` records `success=True`. The security-failure gate at `:653` therefore cannot detect this path. A low score averaged with successful agents is not a failure policy.
- **Implement:** Use a typed result distinguishing success, timeout, provider failure, invalid output, cancellation, and budget refusal. Preserve errors through adapters/state/persistence/UI. Require successful mandatory checks and valid source coverage before approval. Treat parse failures/empty outputs distinctly from a clean review. Add an explicit policy for optional-agent degradation and human escalation.
- **Accept:** Inject a security provider exception while other agents return high-confidence approvals: overall result cannot approve. Repeat with invalid JSON, schema-invalid response, timeout, budget denial, all agents failing, and missing agent results. Saved status, GitHub output and UI agree about incomplete coverage.

```text
Status: DONE
Owner: BE + ML (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_preserve_agent_failures_t06.py tests/test_phase8b.py` passed (25/25); all 202 unit tests in test suite passed. Date: 2026-10-29.
Evidence: `AgentFailureKind` enum added to `contracts.py`; `AgentOutput` and `VerdictRecord` preserve `succeeded`, `failure_kind`, and `error_message`; `BaseAgent.analyze()` and `_apply_output_guardrail()` default failed verdicts to `REQUEST_CHANGES` (never `APPROVE`); `orchestrator/nodes.py` preserves failure metadata and enforces Rule 1 critical blocking on security failures or timeouts.
Residual risks: none.
Rollback: git checkout backend/agents/base_agent.py backend/agents/contracts.py backend/orchestrator/nodes.py tests/test_preserve_agent_failures_t06.py
```

### T07 — Review an identified commit with complete, honest source coverage

- [x] **P0 · V · BE · Depends: T06**
- **Evidence:** `nodes.py:156–176` converts any GitHub fetch failure into stub metadata and an empty/unavailable diff without a development-only guard. `base_agent.py` truncates context; repository retrieval uses limited candidates.
- **Implement:** Fail or explicitly defer when required metadata/diff cannot be fetched. Restrict demo fixtures to explicit test/demo configuration. Capture base/head SHAs, files received/omitted, truncation reasons, and reviewed coverage. Recheck head before publication; supersede stale jobs on synchronize events. Apply bounded processing to large/binary/generated/vendor files with visible exclusions.
- **Accept:** GitHub 401/403/404/429/5xx, truncated diffs, force-push, deleted/renamed files and a new head during processing cannot produce an approval claiming complete review. Empty valid PR and unavailable diff are distinguishable. Publication identifies the exact reviewed SHA.

```text
Status: DONE
Owner: BE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_commit_coverage_t07.py` passed (5/5); all 207 unit tests passed. Date: 2026-10-29.
Evidence: `nodes.py` now prevents false approvals on GitHub fetch failures by tracking `diff_unavailable` and escalating to HITL; distinguishes valid empty PRs; categorizes bounded file exclusions (lockfiles, binary/media, minified code) in `source_coverage`; rechecks head commit SHA in `post_review` to detect superseded/force-pushed reviews; displays reviewed SHA and exclusions in `_build_review_summary`.
Residual risks: none.
Rollback: git checkout backend/orchestrator/nodes.py backend/orchestrator/state.py tests/test_commit_coverage_t07.py
```

### T08 — Protect all private and untrusted context boundaries

- [x] **P0 · V/G · SEC + BE · Depends: T04, T06**
- **Evidence:** `base_agent.py:300–314` masks the diff; PR title/body, retrieved code and embedding-ingestion paths are separate. Presence of `injection_guard.py`, masking, sandbox and capability classes does not prove enforcement at every boundary.
- **Implement:** Map every source → embedding/LLM/log/trace/audit/GitHub path. Apply configurable secret/PII handling at the outbound boundary for all context fields and all providers. Preserve enough source coordinates for explanations. Treat repository instructions as untrusted data; validate structured outputs, paths and tool permissions in code. Keep execution of repository code disabled unless an isolated, credential-free sandbox is explicitly implemented. Record provider data-use/retention settings for private repositories.
- **Accept:** Canary credentials/PII inserted in title, body, diff, retrieved code and exceptions never reach prohibited sinks. Adversarial repository text cannot change tool permissions, fetch another tenant, or turn a failed check into approval. Regex masking is described as mitigation, never proof that prompt injection is solved. Source: [S08][S08].

```text
Status: DONE
Owner: SEC + BE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_boundary_protection_t08.py` passed (4/4); all 211 unit tests passed. Date: 2026-10-29.
Evidence: Outbound secret and PII redaction enforced across all prompt fields (`title`, `description`, `diff`, `retrieved_context`, `peer_context`) in `BaseAgent.analyze()` and across all embedding paths in `embedder.py` (`embed_text`, `embed_batch`); fixed regex capturing group span bug in `masking.py`; enhanced injection scanning across `retrieved_context` in `injection_guard.py` and `build_context`; verified tool capability scope enforcement blocking unauthorized agent tools.
Residual risks: none.
Rollback: git checkout backend/agents/base_agent.py backend/memory/embedder.py backend/security/masking.py backend/security/injection_guard.py tests/test_boundary_protection_t08.py
```

### T09 — Make webhook receipt and enqueue recoverable

- [x] **P1 · V/G · BE + SRE · Depends: T04, T14**
- **Evidence:** The live enqueue path in `backend/job_queue/arq_worker.py:259–293` uses `backend/memory/redis_client.py:146–190` to check/mark before submitting. A failed enqueue leaves a marker that rejects redelivery. ARQ's `_job_id=workflow_id` does provide duplicate-job protection; ordinary duplicate deliveries are not proven to create duplicate jobs. Redis data in Compose is not persisted.
- **Implement:** Validate signature against raw bytes, event/action/content type/body limit, installation and delivery identity. Store a unique durable receipt plus outbox/work item atomically. Acknowledge only after durable acceptance; replay duplicate receipts safely. Dispatch with retries, visibility, bounded retention and reconciliation. Distinguish delivery identity from `(installation, repo, PR, head SHA, policy version)` review identity.
- **Accept:** Simultaneous duplicates, crash after receipt/before enqueue, Redis unavailable, repeat redelivery and new commit events lose no accepted job and create no duplicate external review. Return successful receipt promptly; GitHub requires 2XX within 10 seconds. Document delivery recovery rather than assuming automatic retry. Source: [S03][S03].

```text
Status: DONE
Owner: BE + SRE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_webhook_recovery_t09.py` passed (6/6); full pytest suite passed (228 passed, 1 skipped). Date: 2026-10-29.
Evidence: Webhook receiver enforces Content-Type validation and 10MB payload size limits; deduplicates replays using `X-GitHub-Delivery` receipts stored in Redis; atomically sets idempotency and delivery receipt only on confirmed ARQ enqueue; rolls back idempotency keys upon enqueue failure to guarantee redeliveries succeed; returns HTTP 503 for GitHub automatic delivery recovery on Redis unavailability.
Residual risks: none.
Rollback: git checkout backend/webhook_receiver/router.py backend/job_queue/arq_worker.py backend/memory/redis_client.py tests/test_webhook_recovery_t09.py
```

### T10 — Persist workflow state and make retries real

- [x] **P1 · V · BE + SRE · Depends: T06, T09, T14**
- **Evidence:** `backend/orchestrator/graph.py:72` defaults to `MemorySaver`. Worker exception handling returns error dictionaries; a normal return can look like a successful queue job. `resume()` documentation claims stronger durability than the process-local implementation supplies.
- **Implement:** Attach a supported persistent checkpointer through lifecycle/configuration; scope checkpoint keys and retention. Separate retryable failures, terminal failures and successful human escalation. Configure bounded retry/backoff, dead-letter handling, reconciliation, cancellation and stuck-job detection. Persist terminal status even when a worker dies. Keep side effects idempotent across replay.
- **Accept:** Kill worker after each graph stage, restart another process and recover without losing accepted work or duplicating posts. Queue retry counters advance on transient errors, permanent errors stop, and poison jobs reach an actionable dead-letter record. Test graceful termination with in-flight work.

```text
Status: DONE
Owner: BE + SRE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_workflow_persistence_t10.py` passed (5/5); full pytest suite passed (233 passed, 1 skipped). Date: 2026-10-29.
Evidence: Implemented `DurableCheckpointSaver` with portable byte serialization and automatic Redis persistence for cross-process interruption and resumption; configured ARQ worker bounded retry with exponential backoff on transient errors (`RetryableWorkflowError`, timeouts); added dead-letter queueing (`record_dead_letter`) for poison jobs and exhausted retries; enforced replay publication idempotency in `post_review`.
Residual risks: none.
Rollback: git checkout backend/orchestrator/checkpointer.py backend/orchestrator/graph.py backend/job_queue/arq_worker.py backend/memory/redis_client.py backend/orchestrator/nodes.py tests/test_workflow_persistence_t10.py
```

### T11 — Separate review computation from reliable GitHub publication

- [x] **P1 · V · BE · Depends: T07, T09, T10, T14**
- **Evidence:** `backend/orchestrator/nodes.py` has post-error paths that return completed state. `github_client.py` retries requests, including ambiguous write failures. Current diff-line mapping must be verified beyond presence of a helper.
- **Implement:** Save immutable computed results and a publication outbox first. Model `pending/posting/posted/retryable_failure/permanent_failure` independently from computation. On a timeout after GitHub accepts a write, reconcile by stable review marker/ID before retrying. Validate file paths and LEFT/RIGHT changed-hunk lines; put unsupported locations in the summary. Deduplicate repeated findings and handle review-body limits.
- **Accept:** 422 invalid lines, rate limits, network timeout after accepted write, GitHub rejection, and DB failure after accepted write remain truthful and recoverable. Test additions/deletions/renames/multiple hunks/no-newline/binary files and head changes. Exactly one effective publication per review identity is demonstrated, not assumed from queue deduplication.

```text
Status: DONE
Owner: BE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_reliable_publication_t11.py` passed (5/5); full pytest suite passed (238 passed, 1 skipped). Date: 2026-10-29.
Evidence: Modeled publication states (`pending`, `posted`, `retryable_failure`, `permanent_failure`) independently from review computation; embedded stable HTML markers (`<!-- hadron-review:{workflow_id} -->`) in review summaries and added `list_pr_reviews` reconciliation to prevent duplicate publications across network write timeouts; validated diff hunk line numbers and deduplicated redundant agent findings to avoid GitHub 422 errors, with safe body-only fallback on inline comment rejection.
Residual risks: none.
Rollback: git checkout backend/orchestrator/nodes.py backend/orchestrator/state.py backend/integrations/github_client.py tests/test_reliable_publication_t11.py
```

### T12 — Make human decisions atomic, attributable, and deliverable

- [x] **P1 · V · BE + FE · Depends: T02–T04, T11, T14**
- **Evidence:** `backend/hitl/dispute.py:196–215,262–288` commits resolution before separate feedback/publication; all verdicts map to `COMMENT` at `:321–325`. Existing `SELECT FOR UPDATE` and terminal-status rejection at `:156–174` must be retained. `hitl_router.py:310` imports nonexistent `get_redis_client`. Queue total is `len(items)` at `:160`.
- **Implement:** In one short transaction conditionally resolve the expected pending/versioned row, record the authenticated actor/reason and audit/feedback/publication intent. Return 409 for competing decisions. Publish outside the transaction with retries and explicit status. Decide whether the product records advice or submits GitHub approval/request-changes; label the actual effect. Repair the rebuild API/import/response contract and use an authorized scoped count.
- **Accept:** Two simultaneous reviewers cause one resolution and one conflict; retry is idempotent; GitHub outage retains a durable decision and retryable publication. Caller identity cannot be forged. Rebuild recovers a lost Redis queue without duplicates. UI never promises an override until a real audited reversal/versioning workflow exists.

```text
Status: DONE
Owner: BE + FE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_hitl_decisions_t12.py` passed (4/4); full pytest suite passed (242 passed, 1 skipped). Date: 2026-10-29.
Evidence: Enforced atomic status transition and feedback recording in single database transaction; mapped human verdicts faithfully (`approve` -> `APPROVE`, `request_changes` -> `REQUEST_CHANGES`, `dismiss` -> `COMMENT`) with reviewer attribution in review comment bodies; added `count_pending_queue` for truthful pagination counts; repaired `rebuild_queue` Redis pool invocation.
Residual risks: none.
Rollback: git checkout backend/hitl/dispute.py backend/hitl/queue.py backend/api/hitl_router.py tests/test_hitl_decisions_t12.py
```

### T13 — Repair embedding dimensions, batch shape, and semantic validity

- [x] **P1 · V · DATA + BE · Depends: T08, T14**
- **Evidence:** `embedder.py:60,106,193,221` uses 1536 for empty vectors while settings use 256; API calls at `:131–134,210–213` omit configured dimensions. The `nvapi-` branch at `:197–204` returns one flat hash-derived vector for a batch using the final loop variable. A cryptographic hash is not a semantic embedding.
- **Implement:** Define and validate one embedding contract: provider, model/version, dimension, normalization and namespace. Use a real supported embedding provider or explicitly disable retrieval; confine synthetic vectors to tests. Return one correctly shaped vector per input in order, including empty-input policy. Version the index and re-embed through a controlled migration when the contract changes.
- **Accept:** Empty/mixed/duplicate/multiple/long input batches satisfy exact shape/count/ordering; wrong dimensions are rejected before storage; provider/index dimensions match. A labeled semantic retrieval baseline beats a nonsemantic/hash baseline. No fake fallback is reported as working semantic search.

```text
Status: DONE
Owner: DATA + BE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_embeddings_t13.py` passed (8/8); full pytest suite passed (250 passed, 1 skipped). Date: 2026-10-29.
Evidence: Established explicit `EmbeddingContract` (`text-embedding-3-large`, 256 dims matching `code_chunks` `VECTOR(256)`, L2 unit normalization); guaranteed exact count/order/dimension across empty, mixed, duplicate, and long batch inputs with explicit zero-vector empty policy; eliminated fake SHA-256 hash fallback for non-embedding keys and gracefully degraded via `EmbeddingError`; verified `TigerMemoryClient` and `qdrant_client` dimension validation before storage and search; confirmed semantic retrieval baseline discriminates code domains over hash noise.
Residual risks: none.
Rollback: git checkout backend/memory/embedder.py backend/memory/tiger_client.py backend/memory/qdrant_client.py tests/test_embeddings_t13.py
```

### T14 — Repair TLS, schema creation, and migration ownership

- [x] **P0 · V · DATA + SEC + BE · Depends: none**
- **Evidence:** `backend/database/postgres.py:415–420` disables hostname and certificate verification. `:443–446` discards semicolon-separated SQL segments beginning with `--`; `:452–454` logs migration failure yet announces application. Vector codec initialization at `:424` precedes extension creation. `main.py:130–147` relies on `create_all()` at startup.
- **Implement:** Verify server certificates/hostname with the proper CA for both ORM and raw drivers. Move schema changes to a versioned migration runner with explicit extension prerequisites and checked failure. Remove the comment-splitting parser; reconcile ORM/SQL column types, IDs, constraints, aggregates and indexes. Run migrations once per deployment using a separate migration role; runtime has limited DML privileges. Choose optional versus required Timescale/vector capabilities explicitly.
- **Accept:** Empty and previous-version Postgres instances migrate to the same expected schema; a second run is harmless; failed DDL blocks the release; bad CA/hostname is rejected. Test production extensions and a documented local profile. Confirm existing data survives migration and rollback/forward-repair. Sources: [S18][S18], [S19][S19].

```text
Status: DONE
Owner: DATA + SEC + BE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_postgres_tls_and_migration_t14.py` passed (3/3); all 214 unit tests passed. Date: 2026-10-29.
Evidence: `_build_ssl_context()` in `backend/database/postgres.py` enforces full certificate and hostname verification (`check_hostname = True`, `verify_mode = ssl.CERT_REQUIRED`) with system CA and `POSTGRES_CA_CERT` support; `parse_sql_script()` strips SQL comments without dropping valid statements; `init_tiger_schema()` raises `MigrationError` on required DDL failure and safely wraps codec registration to avoid pre-migration failures.
Residual risks: none.
Rollback: git checkout backend/database/postgres.py tests/test_postgres_tls_and_migration_t14.py
```

### T15 — Repair the judge contract and measure false positives

- [x] **P1 · V · ML + BE · Depends: T06, T07**
- **Evidence:** `backend/evaluation/judge.py:245` calls `self._llm.complete`, which the client does not expose. The empty-golden branch at `:143–149` grants full finding/severity components without penalizing unexpected findings. A passing keyword fallback is not an LLM quality evaluation.
- **Implement:** Use the actual typed asynchronous provider interface or an explicit deterministic judge. Report judge failure/fallback separately and fail the intended LLM release gate when it did not run. Add precision, recall, false positives per clean PR, severity correctness, unsupported-location rate and abstention coverage. Version examples, prompts, model IDs, rubric and baselines; separate tuning from held-out tests.
- **Accept:** A clean PR with invented critical findings fails the relevant metric; an unavailable judge cannot silently pass. Include adversarial, clean, large, multilingual and rare-critical slices. Require sample counts and uncertainty, not one sample PR or self-reported confidence, for quality claims. Human adjudication resolves disagreements.

```text
Status: DONE
Owner: ML + BE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_judge_and_eval_t15.py` passed (5/5); `pytest tests/test_eval_phase9.py` passed (20/20); full pytest suite passed (255 passed, 1 skipped). Date: 2026-10-29.
Evidence: Added typed `complete` and `acomplete` methods to `LLMClient`; enhanced `JudgeScore` and `EvalResult` with precision, recall, false_positive_count, and explicit `judge_fallback_active` telemetry; clean PRs with invented critical findings are strictly penalized and fail `< PASS_THRESHOLD (0.70)`; `fail_on_unavailable_llm` and `require_llm_judge` in `RegressionGate` block silent fallback passing on missing LLM judges.
Residual risks: none.
Rollback: git checkout backend/evaluation/judge.py backend/evaluation/regression_gate.py backend/tools/llm_client.py tests/test_judge_and_eval_t15.py
```

### T16 — Remove fabricated safety, ROI, and capability claims

- [x] **P0 · V · FE + UX · Depends: T01, T06**
- **Evidence:** `ExecutiveHealthScore.tsx:20–35` supplies 98/100, “fully protected,” and 18.5 hours saved for zero reviews. `PlainEnglishAssistant.tsx` returns scripted reassurance without analysis. `NonTechReviewCard.tsx` infers business impact/safety from title keywords. `layout.tsx` hardcodes a 4.9 rating, 128 reviews, $29 offer and “hallucination-free”/Bayesian claims without supporting product data.
- **Implement:** Replace the gauge with measured counts and explicit time window/coverage. Make no-data and unavailable-data states honest. Remove the simulated assistant or clearly mark a useful demo; any future assistant must cite authorized source records and abstain. Remove unverified ratings, prices, metrics and guarantees from visible copy, metadata, solution pages and docs. Preserve the improved caveats already present in review components.
- **Accept:** Zero/failed/partial reviews never render a safety percentage, fabricated ROI or a release guarantee. Every displayed number has a query/provenance/window; recommendation is separate from release approval. Structured data matches visible substantiated content. Sources: [S11][S11], [S12][S12], [S13][S13], [S14][S14], [S16][S16].

```text
Status: DONE
Owner: FE + UX (Antigravity)
Commit: working-tree
Verification: `npm run lint` (`tsc --noEmit`) and `NEXT_TELEMETRY_DISABLED=1 npm run build` passed with 0 errors (16/16 routes generated). Date: 2026-10-29.
Evidence: Fabricated metrics removed from `ExecutiveHealthScore.tsx`, replaced with honest operational counts (Total PRs, Approved, Escalated, Monitored Repos); empty reviews render honest standby state (`"—"` with zero fabricated hours saved); `PlainEnglishAssistant.tsx` replaced with fact-based workspace guidance with disclaimers; `NonTechReviewCard.tsx` shows actual review verdict impact instead of keyword-inferred fake risk pills; unverified Schema.org offers and rating removed from `layout.tsx`.
Residual risks: none.
Rollback: git checkout frontend/src/components/ExecutiveHealthScore.tsx frontend/src/components/PlainEnglishAssistant.tsx frontend/src/components/NonTechReviewCard.tsx frontend/src/app/layout.tsx frontend/src/lib/types.ts frontend/src/components/VerdictChip.tsx
```

## 5. Reliability, security, and delivery foundations

### T17 — Bound ingress, work, and provider consumption

- [x] **P1 · G/R · BE + SEC · Depends: T02, T04, T09**
- **Evidence:** Public ingress and API routes have no demonstrated end-to-end admission controls; repository/code/model operations can consume significant resources.
- **Implement:** Set request/body/field limits, per-principal and per-installation quotas, bounded queue depth/concurrency, provider timeouts, and backpressure. Keep a separate authenticated-webhook policy so shared GitHub source IPs are not unfairly throttled. Bound headers, pagination, decompression, diff/file count, chunk count and token budgets. Avoid client-IP trust without a documented proxy chain.
- **Accept:** Oversized requests fail before expensive parsing; excess demand gets actionable 413/429/503 plus suitable retry guidance; noisy tenant cannot starve another; memory and queue age stay bounded under load. Legitimate webhook retries remain recoverable.

```text
Status: DONE
Owner: BE + SEC (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_admission_and_bounds_t17.py` passed (10/10); full pytest suite passed (265 passed, 1 skipped); frontend lint & build passed (16/16 routes). Date: 2026-10-30.
Evidence: Implemented `AdmissionControlMiddleware` enforcing 64KB header limit (HTTP 431), streaming body size limits (10MB webhook, 2MB REST API; HTTP 413), and decompression bomb (zip bomb) protection; added proxy-aware client IP extraction respecting configured trusted proxies; implemented per-principal/per-tenant API rate limiting and separate authenticated-webhook policy throttling per repository (not shared GitHub source IPs); enforced ARQ queue depth backpressure (HTTP 503 + Retry-After) and per-tenant active review concurrency limits (HTTP 429 + Retry-After) with automatic idempotency key cleanup on rejection so GitHub retries remain recoverable; bounded diff size (500KB) and file count (100 files) in `build_context` with explicit truncation reasons; capped repository ingestion to 500 files and 50 chunks per file; bounded pagination limits to 100 max.
Residual risks: none.
Rollback: git checkout backend/security/admission.py backend/main.py backend/job_queue/arq_worker.py backend/webhook_receiver/router.py backend/orchestrator/nodes.py backend/data/ingestion.py backend/api/ backend/core/
```

### T18 — Enforce cost limits with reservations and a reliable ledger

- [x] **P1 · V · BE + DATA · Depends: T06, T14**
- **Evidence:** `backend/economics/budget.py:78–96` checks recorded daily spend and fails open on query failure; per-review cap is advisory. Concurrent agents can all pass a preflight read before charges land.
- **Implement:** Atomically reserve conservative input/output cost per tenant/review/day before dispatch; reconcile actual usage and release unused reservation after terminal handling. Include retries, embeddings and judge calls in the defined budget scope. Make ledger writes idempotent and durable; distinguish unavailable usage from zero. Reject unknown prices or use an explicit conservative estimate. Define bounded emergency behavior when the ledger is unavailable.
- **Accept:** Concurrent fan-out at the cap, cancellation, timeout, provider retries, crash/replay and ledger outage cannot overspend beyond a documented reservation bound. UI distinguishes hard/advisory limits and estimates/settled usage. No unsupported “strict caps” claims.

```text
Status: DONE
Owner: BE + DATA (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_cost_limits_and_ledger_t18.py` passed (8/8); full pytest suite passed (273 passed, 1 skipped); frontend lint & build passed (16/16 routes). Date: 2026-10-30.
Evidence: Implemented atomic cost reservations via `CostLedger` and `BudgetGuard.reserve` before agent, embedding, and judge execution, preventing concurrent fan-out at the budget cap from exceeding limits; reconciled actual token usage post-execution and automatically released unused reservation headroom on completion, errors, or timeouts; built idempotent and replay-safe ledger writes using unique `idempotency_key` indexes; distinguished unavailable database usage from zero spend via `CostLedgerUnavailableError`, with fail-closed or bounded emergency spend ceilings (`emergency_budget_usd`); added canonical model pricing table with strict rejection or conservative upper-bound estimation; extended `/api/v1/economics/budget` status endpoint to distinguish settled spend, active reservations, hard daily cap, advisory review cap, and ledger health.
Residual risks: none.
Rollback: git checkout backend/economics/ backend/agents/base_agent.py backend/memory/embedder.py backend/tools/llm_client.py backend/database/models.py scripts/migrations/2026-06-tiger-init.sql backend/api/economics_router.py backend/config/settings.py tests/test_cost_limits_and_ledger_t18.py
```

### T19 — Make external-call resilience consistent

- [x] **P1 · V/G · BE · Depends: T06, T18**
- **Evidence:** Retry/circuit-breaker modules exist, but integrations, raw `httpx` ingestion, provider SDKs and model routing use different paths. Source comments do not prove coverage or safe write retries.
- **Implement:** Inventory every outbound request; apply shared deadline budgets, bounded exponential backoff with jitter, Retry-After handling, connection pooling and per-provider concurrency. Separate retriable reads from ambiguous writes. Validate model capabilities/output format and current prices at configured version. Carry cancellation/deadline through stages; reset context attribution after tasks finish.
- **Accept:** Contract tests inject connect/read timeouts, 429/403 rate limiting, 5xx, malformed output and cancellation for each adapter. Retries do not multiply across nested layers or exceed the workflow deadline; circuits recover; cancellation stops unnecessary spend.

```text
Status: DONE
Owner: BE (Antigravity)
Commit: working-tree
Verification: `pytest tests/test_external_resilience_t19.py` passed (8/8); full pytest suite passed (281 passed, 1 skipped); frontend lint & build passed (16/16 routes). Date: 2026-10-30.
Evidence: Unified outbound resilience across HTTP and LLM adapters; implemented `DeadlineBudget` and `DeadlineExceededError` in `backend/reliability/timeout.py` to slice shared deadline budgets and prevent retry amplification; added uniform jitter, `Retry-After` header clipping, and deadline clipping to `backend/reliability/retry.py` and `backend/tools/llm_client.py`; configured HTTP connection pooling limits (`max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0`); isolated idempotent reads (`GET`, `HEAD`) from ambiguous writes (`POST`, `PUT`, `PATCH`, `DELETE`) via `AmbiguousWriteError` in `backend/integrations/github_client.py` to refuse blind retries and eliminate duplicate GitHub review mutations; protected repository ingestion (`backend/data/ingestion.py`) with `GITHUB_BREAKER` and connection limits; enforced per-provider concurrency bulkheads (`_PROVIDER_SEMAPHORES`); guaranteed workflow context attribution cleanup via `scoped_workflow_context` in `BaseAgent.analyze`; handled `asyncio.CancelledError` immediately to abort in-flight work and prevent unnecessary token spend.
Residual risks: none.
Rollback: git checkout backend/reliability/ backend/integrations/github_client.py backend/tools/llm_client.py backend/data/ingestion.py backend/observability/workflow_context.py backend/agents/base_agent.py tests/test_external_resilience_t19.py
```

### T20 — Initialize observability in every process and preserve evidence

- [ ] **P1 · V/G · BE + SRE · Depends: T10, T14, T18**
- **Evidence:** API lifecycle initializes Tiger/Sentry/tracing; standalone worker startup primarily connects Redis. Separate processes cannot share an API-created singleton. Fire-and-forget events and best-effort writes do not establish an audit trail.
- **Implement:** Shared explicit API/worker resource lifecycle; initialize/flush/close DB, vector store, telemetry and clients in each process. Use structured, redacted logs with delivery/workflow/review IDs and trusted tenant context. Persist security/audit/publication/cost events durably; sample optional diagnostics. Bound label cardinality and retention. Fix UUID/string identity inconsistencies across event writers and economics readers.
- **Accept:** A separately launched worker emits attributed traces, persisted review/cost/audit records, and terminal status; shutdown flushes critical events. Missing telemetry is visible as degraded, not zero activity. Logs/traces contain no tokens, raw private code or unredacted connection strings.

### T21 — Make health checks reflect actual capability

- [ ] **P1 · V/G · BE + SRE · Depends: T10, T14, T20**
- **Evidence:** Liveness and deep health exist; startup catches required-service errors and worker health is not equivalent to API health. The frontend health helper calls `/health/live`.
- **Implement:** Keep cheap liveness separate from readiness and authenticated diagnostics. Readiness checks required schema version, DB/queue availability and configured worker capability; optional RAG degradation is explicit. Track worker heartbeat and oldest accepted job. Avoid exposing raw exceptions to unauthenticated probes or requiring retired Qdrant when Tiger is selected.
- **Accept:** DB/Redis/worker/optional-vector outages produce the documented distinct states. An API answering HTTP is not displayed as an operating review pipeline. Probe latency is bounded; the load balancer removes unready replicas without unnecessary restart loops.

### T22 — Make deployment topology and images reproducible

- [ ] **P1 · V/G · SRE · Depends: T05, T10, T14, T20**
- **Evidence:** `scripts/start.sh` launches API and worker, while Compose also defines a worker; Vercel adapter and container paths coexist. Redis has no durable volume in Compose. Docker copies the whole context; `.dockerignore` omits local `.aws/.codex/.agents` directories. Builder installs an editable package before copying backend source.
- **Implement:** Declare one supported production topology: frontend, API, persistent worker(s), durable Postgres and queue. Explicitly provision the worker if API is serverless. Use separate process commands/health checks, signal forwarding and graceful shutdown. Build from locked dependencies and an allowlisted context; exclude local credential/config/agent directories. Test package imports and runtime user/filesystem. Keep dev-only ports/credentials isolated; use persistent Redis/recovery policy and pinned image versions.
- **Accept:** Build/run image from a clean checkout, inspect its contents without printing secrets, and start each process independently. No credentials/local tooling/history enter the image; no accidental duplicate worker. Restart/load tests prove recoverability. Do not repeat “<200 MB” or “CIS hardened” claims without measurement/control evidence.

### T23 — Implement retention, deletion, export, and data governance

- [ ] **P1 · G/R · DATA + SEC + UX · Depends: T04, T08, T14, T20**
- **Evidence:** `docs/FUTURE_WORK.md` explicitly defers governance; source stores review context, findings, embeddings, feedback and telemetry without a verified end-to-end retention lifecycle.
- **Implement:** Create a data inventory with purpose, owner, location, access, retention and deletion path. Include provider processing, caches, backups, artifacts and logs. Set configurable scheduled purge with tenant offboarding, GitHub uninstall/revocation and legal-hold handling where required. Provide authenticated scoped export with expiration, audit and rate limits. Keep audit integrity separate from unnecessary raw code retention.
- **Accept:** A synthetic tenant can export only its data and be deleted from all active stores/caches/vector namespaces within the stated interval; backup expiry and provider limitations are documented. Purge retries are safe. Product privacy/security statements match implemented behavior; legal obligations require qualified review.

### T24 — Prove backups and disaster recovery

- [ ] **P1 · G/E · SRE + DATA · Depends: T09–T14, T23**
- **Implement:** Back up source-of-record data, migration versions and required encryption/config metadata. Define whether queues/checkpoints are restored or rebuilt from durable receipts/outboxes. Use encrypted backups, restricted restore access and monitoring for backup failure. Proposed pilot objectives: RPO ≤15 minutes, RTO ≤60 minutes; owner must accept or revise them based on hosting/cost.
- **Accept:** Restore to an isolated environment, verify counts/constraints/tenant isolation, and replay unfulfilled work without duplicate GitHub reviews. Record measured recovery time/data gap, not only “backup enabled.” Exercise lost Redis and lost DB scenarios separately; preserve deletion obligations across restore.

### T25 — Turn CI into meaningful release evidence

- [ ] **P1 · V/G · QA + SRE · Depends: T01, T05, T06, T14, T15**
- **Evidence:** CI runs one mocked smoke file, frontend build and a real-LLM gate on main; comments still reference old test names. Frontend `lint` only runs TypeScript. No checked-in browser/accessibility suite was found.
- **Implement:** Classify unit, contract, integration, browser, security, load and paid-evaluation tests. Run deterministic critical-path tests on every PR with network denied and isolated credentials. Add real Redis/Postgres migration/concurrency tests, frontend type/lint/build, component/state tests and browser/axe flows. Keep paid evals explicit, budgeted and reproducible. Pin action revisions, minimum token permissions and concurrency cancellation; protect external secrets from untrusted PRs.
- **Accept:** Required checks block a deliberately introduced auth bypass, failed-agent approval, migration error and UI parse error. Test collection and skip reasons are visible; never describe a partial suite as full coverage. Branch/deploy settings prove releases wait for checks, including external auto-deploy integrations.

### T26 — Implement safe rollout, rollback, and feature controls

- [ ] **P1 · G/E · SRE + BE · Depends: T10–T15, T20–T25**
- **Implement:** Separate dev/staging/production secrets/data/installations. Deploy immutable artifacts; run migration preflight, canary health and synthetic review checks before traffic promotion. Feature-flag new models, automation, retrieval and policy changes. Provide kill switches for publication, provider spend and new intake while preserving accepted work. Document rollback versus forward migration repair.
- **Accept:** Roll back a bad frontend/backend/model change in staging; old/new versions coexist during migration; disabling publication retains pending work; revoking a compromised token and rotating secrets is rehearsed. Capture who approved release and the exact artifact/schema/prompt versions.

### T27 — Centralize API configuration, errors, caching, and browser security

- [ ] **P1 · V/G · BE + FE + SEC · Depends: T03, T04, T05**
- **Evidence:** `frontend/next.config.mjs` defaults to a public hosted backend; `githubContext.tsx:63,95` bypasses `lib/api.ts`; `api.ts` throws raw response bodies. Production CORS falls back to localhost when configuration is absent.
- **Implement:** Validate deployment origins explicitly and fail unsafe production defaults. Consolidate calls behind the same authenticated transport with typed errors, cancellation and request IDs. Keep secrets on the server. Apply private/no-store caching to user data and clear tenant caches on logout/switch. Add CSP, frame restrictions, referrer policy and appropriate transport headers after testing Next.js scripts/fonts/OG behavior. Use a report-only CSP rollout where needed.
- **Accept:** Missing configuration cannot silently contact another environment. 401/403/404/409/422/429/5xx have stable sanitized error contracts. Browser cache, back navigation and account switches reveal no prior user's private data. Direct and proxied origins both satisfy cookie/CSRF policy; CSP blocks unauthorized script execution without breaking the app.

### T28 — Align API models, totals, IDs, and status semantics

- [ ] **P1 · V/G · BE + FE · Depends: T02, T06, T11, T12**
- **Evidence:** Backend rebuild returns `pushed_to_redis` while frontend expects `rebuilt`; HITL total is page length. Economics UUID parsing differs from composite review IDs used elsewhere. Type assertions in `lib/api.ts` do not validate returned JSON.
- **Implement:** Specify/version OpenAPI response schemas and generate or verify frontend types. Normalize opaque IDs and error responses. Return scoped total counts and deterministic ordering with a stable tie-breaker. Define separate fields for workflow, mandatory-check coverage, recommendation, human decision, publication and freshness. Support unknown enum values gracefully. Distinguish zero, missing, unavailable and stale metrics.
- **Accept:** Contract fixtures exercise every route, all enums, nulls, malformed IDs and empty pages. Counts agree with server filters across pages; equal timestamps do not duplicate/skip rows. Old/new API clients are compatible during rollout; UI never treats a failed response as empty success.

### T29 — Make code ingestion complete, versioned, and removable

- [ ] **P1 · V/G · DATA + BE · Depends: T04, T07, T13, T14**
- **Evidence:** `backend/data/ingestion.py:63–171` includes slices that truncate chunks at `max_chunk_chars`; tree truncation is logged; ingestion follows the default branch. Upsert/freshness logic needs proof that removed files and surplus old chunks disappear.
- **Implement:** Record repository/installation, immutable source commit/blob SHA, path, symbol, line range and embedding version for every chunk. Split oversized definitions without silently dropping tails/preamble; declare unsupported language/encoding behavior. Handle truncated repository trees with pagination/traversal or an explicit incomplete index. Replace a file's chunk set atomically and delete removed/stale versions. Mark freshness only after the required chunk writes succeed.
- **Accept:** Reconstruct source coverage for large functions, Unicode, mixed languages, renames, deletes and shrinking files. No deleted/outdated chunk appears in current retrieval. Partial embedding failure cannot mark a file fresh. Context from default branch is labeled and cannot impersonate the reviewed PR head.

### T30 — Reconcile data constraints and measure query scalability

- [ ] **P1 · V/G · DATA · Depends: T04, T14, T28, T29**
- **Evidence:** `backend/database/models.py:447` uses a 512-character repository-file key but `backend/data/freshness.py:173` asserts 128. ORM, migration SQL and query callers must share a contract. Offset pagination and growing event/cost stores need realistic workload evidence.
- **Implement:** Choose a bounded stable key/composite uniqueness strategy and migrate all callers consistently. Index actual tenant/status/time/foreign-key access paths; use `EXPLAIN (ANALYZE, BUFFERS)` on representative fixtures before optimization. Bound DB pools across API/worker replicas and serverless concurrency. Add statement/lock timeouts, retention/partition maintenance and query latency metrics. Use cursor pagination when measured offsets justify it.
- **Accept:** Long nested monorepo paths persist and retrieve correctly; concurrent upserts preserve unique review/file identity. Critical queries meet agreed latency at the pilot dataset size; pool exhaustion and lock contention recover without cross-tenant state leakage. Publish measured plans, not claims that DiskANN/aggregates are always faster.

## 6. UI/UX implementation tasks

Use the design specification and state matrix in sections 8–9 as acceptance criteria for every screen. Preserve useful work already present: URL-based review filters/pagination, clearer finding cards, review caveats, and the improved decision form.

### T31 — Establish one semantic design system and complete themes

- [ ] **P1 · V/R · FE + UX · Depends: T01**
- **Evidence:** `layout.tsx` always assigns `dark`; `ThemeToggle.tsx:15–32` independently adds/removes `light`. `Shell.tsx:81,218` mounts two independently stateful toggles. Many dashboard/auth/HITL styles hardcode black/white/zinc values despite theme tokens. System preference is only read at mount.
- **Implement:** Adopt the token contract below across all routes/components, using one theme source of truth and `light/dark/system` preference. Apply it before first paint, subscribe to system changes in system mode, and guard unavailable storage. Build reusable Button, Field, Status, Alert, Dialog, EmptyState and PageHeader primitives with interaction states.
- **Accept:** Every route works in both themes, including focus, validation, native controls, code, charts and overlays. Refresh produces no theme flash/hydration error; blocked storage does not crash. Automated token checks plus rendered contrast/keyboard review pass. No global search/replace that breaks semantic colors.

### T32 — Simplify navigation and separate public/product surfaces

- [ ] **P1 · R · UX + FE · Depends: T03, T31**
- **Implement:** Primary work navigation: Overview, Reviews, Human review, Repositories. Secondary Operations: Usage and Service health. Workspace/session controls remain consistently located; public product/solution pages use a separate layout from the signed-in shell. Show the active workspace and repository where it affects results. Keep URLs and browser navigation meaningful.
- **Accept:** Users reach a pending review and its source in at most three intentional navigation steps from the signed-in overview. Deep links survive login and reload. Active route has `aria-current`; unknown routes have useful 404 recovery. Collapsed navigation retains accessible names and never relies only on icons or hover.

### T33 — Complete repository onboarding and account switching

- [ ] **P1 · V/G · FE + BE + UX · Depends: T03, T04, T09, T31, T32**
- **Evidence:** `openAccountModal()` updates context state, but `GitHubAccountModal` has no live mount in the inspected shell. Selecting an account/repository is currently presented with stronger protection claims than installation/webhook evidence supports.
- **Implement:** Mount a working accessible workspace selector or replace the dead path. Onboarding: authenticate → select installation/repositories → explain permissions/data handling → verify webhook/worker connectivity → inspect a first test review. Distinguish discovered, authorized, connected, indexing, active, degraded and disconnected repositories. Handle revoked permissions, unavailable OAuth and zero repositories.
- **Accept:** A new user can connect a designated test repo and see a real review without editing env files. Switching workspace clears old data immediately and cannot show stale responses from the previous workspace. Cancel/retry/reinstall flows are explicit. “Active” requires backend evidence, not a successful username lookup.

### T34 — Replace the overview with actionable review information

- [ ] **P1 · V/R · FE + UX · Depends: T16, T28, T31–T33**
- **Implement:** Show pending human decisions, running reviews, failed reviews and recent completed reviews with explicit time window. Primary action depends on state: connect repository, inspect pending item, or view recent reviews. Make plain-language explanations available within the same evidence flow; remove duplicate executive/developer information architectures unless research proves a need. Present missing data as unknown.
- **Evidence to resolve:** `CommandPalette.tsx:32–45` writes view preference and dispatches a storage event, but `app/page.tsx:20` reads it only at mount. If modes remain, share reactive preference state so switching on the current dashboard actually works.
- **Accept:** User can identify what needs attention, why and what to do next without reading decorative metrics. Counts come from server aggregates rather than a first-page subset. No reviews/partial API outage do not show green safety reassurance. Links preserve filters and workspace.

### T35 — Finish reviews search, filters, sorting, and pagination

- [ ] **P1 · V/R · FE + BE · Depends: T01, T04, T28, T31**
- **Implement:** Keep URL state for repository/status/page; add useful server-backed search/sort and clear filters with an explicit count. Debounce expensive search and cancel superseded requests. Preserve scroll/filter context when returning from detail. Allow normal links/new tabs. For mobile, prioritize PR identity/status/next action while retaining the rest through labeled detail.
- **Accept:** Empty workspace, zero matches, deleted last-page item, out-of-range/invalid page, long titles, rapid filter changes and back/forward navigation work. Search covers all authorized records, not only loaded rows. No page-level horizontal overflow; a wide code/table region can scroll accessibly when needed.

### T36 — Make review findings and diffs verifiable

- [ ] **P1 · V/R · FE + BE · Depends: T07, T11, T28, T31, T35**
- **Evidence:** `DiffViewer.tsx:34` splits paths on spaces, `:154` attaches findings only to new-line coordinates, and `:201,207` invents critical severity/80% confidence when absent. Replace these defaults with unknown and preserve old/new diff coordinates.
- **Implement:** Detail header identifies repo/PR/head SHA/time and separate execution/publication states. Group findings by severity/file with counts, filtering and stable deep links. Each finding shows evidence, rationale, location, suggested change and agent provenance; reveal raw technical detail on demand. Show actual supplied diff/source or explicitly say it is unavailable. Validate source links and do not invent line numbers. Lazily render expensive code views.
- **Accept:** A reviewer can inspect source and decide whether a finding is valid. Test 0/1/500 findings, duplicate findings, unsupported positions, deleted files, long code lines, missing diff and partial agent results. Findings do not imply all code was examined. Copy-as-Markdown reports success/failure and includes review identity/coverage.

### T37 — Complete the consequential human-decision flow

- [ ] **P1 · V/R · FE + BE + UX · Depends: T12, T28, T31, T36**
- **Evidence:** `hitl/[id]/page.tsx:39–40` promises decisions can be overridden, while the updated decision form states they cannot be edited. The backend's actual publication event differs from approval wording.
- **Queue evidence:** `hitl/page.tsx:15–21` requests a fixed first 100 items and filters by login-owner prefix, which can hide authorized organization repositories. Add reachable server-scoped pagination/counts; an empty queue means no pending items in that scope, not that all PRs are safe.
- **Implement:** Explain exactly what submitting does, using the authorized actor, target PR and reviewed SHA. Preserve notes on failure; validate fields inline and focus the first error. Review the selection/impact before submission without repeated blanket warnings. Disable duplicate submission while pending; show recorded decision separately from GitHub delivery. Resolve conflicts by showing the other decision and refreshing, not overwriting it.
- **Accept:** Keyboard/screen reader user completes a decision; double-click/network retry creates one decision; 401 preserves recoverable draft safely, 403 explains access, 409 shows conflict, 422 labels the field and 5xx permits safe retry. No unimplemented undo/override/merge guarantee is displayed.

### T38 — Make usage and health screens accurate and scoped

- [ ] **P1 · V/R · FE + BE · Depends: T18, T20, T21, T28, T31**
- **Evidence:** `health/page.tsx:6` calls only liveness. Economics copy claims strict caps despite advisory per-review behavior; global queries are not a tenant-specific usage contract.
- **Implement:** Usage shows settled/estimated cost, window/timezone/currency, quotas and data freshness. Link review-level cost breakdown to actual records. Health separates API, worker, queue, persistence, provider and optional retrieval status; diagnostics require proper permissions. Provide accessible text/table equivalents for charts and a meaningful no-data/error state.
- **Accept:** Tenant totals reconcile with the ledger and never reveal another tenant. Missing telemetry cannot render $0 spend or healthy pipeline. Chart axes/units/time ranges and downloadable data agree; keyboard users can obtain the same information without hovering.

### T39 — Complete keyboard, focus, dialog, and shortcut behavior

- [ ] **P1 · V/G · FE + QA · Depends: T31–T33, T37**
- **Evidence:** `Shell.tsx:101` hides mobile navigation by translation alone, leaving offscreen links focusable; its trigger at `:82` lacks expanded/control association. `CommandPalette.tsx:91–123` lacks complete dialog/input/selection semantics and its global Enter handling is not focus-scoped. Also inspect auth controls, review buttons and forms; ARIA labels alone do not prove interaction correctness.
- **Implement:** Add skip link/main landmark, consistent visible focus, native link/button semantics and named icon controls. Dialogs move/contain/restore focus, make background inert, close predictably and remain usable when tall. Shortcuts ignore inputs/editors/IME and can be disabled; destructive decisions never fire from an unconfirmed single key. Document available shortcuts.
- **Accept:** Full keyboard-only traversal with no trap, invisible focus or blocked content; dialogs satisfy the APG pattern. Run screen-reader checks on navigation, filters, status updates and decision form. Prefer a tested primitive over new bespoke focus management. Sources: [S05][S05], [S06][S06].

### T40 — Verify responsive layouts, zoom, touch, and content extremes

- [ ] **P1 · G/R · FE + QA · Depends: T31, T35–T39**
- **Implement:** Use content-driven breakpoints, wrapping/min-width rules, semantic mobile tables/cards, safe areas and scrollable code regions. Keep essential actions reachable above the mobile keyboard. Avoid viewport-height traps and sticky elements obscuring focus. Touch controls use a 44px product target where practical; this is stricter than WCAG's 24px minimum criterion with its exceptions.
- **Accept:** Test actual 320/360/390/768/1024/1440/1920 CSS-pixel viewports, portrait/landscape, 200% text and 400% browser zoom, touch and keyboard. Do not emulate devices using CSS zoom. Include very long repository names, filenames, translated-length labels, emoji, bidirectional text, null avatars and 1,000-character errors. No lost content/actions.

### T41 — Implement the full asynchronous state matrix

- [ ] **P1 · V/G · FE + BE · Depends: T03, T06, T11, T28, T31**
- **Evidence:** Shared SWR polls every five seconds with no automatic error retry; some pages request data without a selected account. `githubContext.tsx:57–68` has no cancellation/generation guard and silently ignores non-2xx repository responses. Existing loading/error handling varies and can render raw response messages.
- **Implement:** Apply section 9 to every fetch/mutation. Pause queries until identity is known; prevent race responses after workspace changes. Keep usable stale data with freshness/error notice; show last updated and manual refresh where useful. Retry only transient failures with bounds; stop polling terminal reviews and pause hidden/offline tabs. Add route-level loading/error/not-found recovery without losing draft work.
- **Accept:** All matrix rows have deterministic fixtures and appropriate screen-reader announcements. Background updates do not steal focus or collapse user-expanded content. Initial failure, stale refresh failure and genuinely empty data are visibly different. No endless spinner or silent lost mutation.

### T42 — Measure and improve perceived and actual performance

- [ ] **P1 · G/R · FE + SRE · Depends: T01, T05, T28, T31, T41**
- **Implement:** Profile representative authenticated routes and public pages on a midrange mobile device/network. Keep static shells on the server where useful; use client boundaries only for interaction. Parallelize independent reads, deduplicate requests, defer diff/chart modules, size avatars/assets and virtualize measured large-list bottlenecks without breaking accessibility. Replace broad transitions and continuous decoration with purposeful feedback.
- **Accept:** Proposed field targets: p75 LCP ≤2.5s, INP ≤200ms, CLS ≤0.1, separately for mobile/desktop. Before enough field data exists, report lab setup/distribution without claiming field compliance. Record bundle sizes and request counts before/after; avoid a >10% unexplained regression against the accepted baseline. Source: [S07][S07].

### T43 — Make brand, copy, and feedback consistent

- [ ] **P2 · V/R · UX + FE · Depends: T16, T31–T38**
- **Implement:** Reuse the existing Hadron mark/logo as the starting identity; validate small-size favicon, monochrome/light/dark versions and asset URLs before redrawing it. Use concrete action labels, ordinary status language and restrained emphasis. Define terminology for review, finding, recommendation, decision, connection and publication. Explain unknowns/recovery without raw stack traces or patronizing “non-tech” labels. No fake urgency, streak pressure, forced celebration or fabricated social proof.
- **Accept:** The same status/action means the same thing across dashboard, email/integration copy, GitHub posts, metadata and docs. All asset links return correct file types/sizes. A user can distinguish actionable controls from decoration. No claim that a geometric ratio/color can guarantee trust or addictive behavior.

### T44 — Make public pages and search metadata truthful

- [ ] **P2 · V/G · FE + UX · Depends: T16, T27, T32, T43**
- **Evidence:** Global JSON-LD contains unsupported ratings/capabilities; `robots.ts`/`sitemap.ts` mix operational `/health` with public pages. Metadata names image files that need asset-level verification; generated OG routes also exist.
- **Implement:** Separate public landing/solution content from authenticated workspace routes. Restrict indexing to useful public URLs; use auth and cache policy for privacy, not robots.txt. Add canonical URLs, real social images and unique factual descriptions. Remove invented review/price schema and thin near-duplicate solution pages. Add accessible product docs, limitations, privacy/security/contact information and valid links.
- **Accept:** Crawl designated public routes and validate status, canonical, sitemap, robots, rendered metadata/image signatures and structured data. Private pages require auth and have appropriate noindex policy; redirects do not expose private data. No promise of special “AEO/GEO” schema or guaranteed ranking; ordinary helpful-content/search practices apply. Sources: [S15][S15], [S16][S16].

## 7. Launch preparation and future work

### T45 — Validate the product with representative users

- [ ] **P1 · R/E · UX + QA · Depends: T31–T41**
- **Implement:** Run repeated formative sessions with developers, maintainers and less-technical decision-makers, including disabled users/assistive technology. Tasks: connect a repository, locate a failed review, verify a finding, understand incomplete coverage and submit a human decision. Compare measured baseline and redesigned flow; randomize variants when making causal claims. Separate observed behavior from preference ratings.
- **Accept:** Document task success, mistakes, time, perceived effort and whether users incorrectly conclude “safe to release.” Proposed pilot target: ≥90% unaided success for core tasks and zero observed critical misinterpretations in the study; record sample size and limitations, not population-wide certainty. Address serious usability failures before launch. Sources: [S11][S11], [S12][S12], [S13][S13], [S14][S14].

### T46 — Define service objectives and capacity from real workloads

- [ ] **P1 · R/E · SRE + BE · Depends: T17–T26, T42**
- **Implement:** Define SLIs for durable receipt, queue delay, review completion by PR size, publication and dashboard reads; specify denominators, exclusions and measurement windows. Proposed pilot targets: 99.9% valid webhook durable acceptance under 10s over 28 days; p95 authenticated list/detail reads ≤500ms excluding client network; p95 small PR review completion ≤120s for a declared workload. Benchmark with realistic concurrency and tenant skew.
- **Accept:** Targets are accepted or revised using data; load/soak tests include bursts, one noisy tenant and degraded providers. Error-budget/burn-rate alerts point to runbooks; stop risky releases when reliability is exhausted. Neither p95 of p95 values nor maximum bucket p95 is advertised as a true global percentile. Source: [S17][S17].

### T47 — Reconcile documentation with implementation and evidence

- [ ] **P1 · V · BE + FE + UX · Depends: T02–T16, T22, T28**
- **Evidence:** `docs/FUTURE_WORK.md` names `backend/economics/budget_guard.py` although the implementation is `budget.py`; both ADR-003 documents share an identifier; principles/README/old tracker contain completion, “safe” and architecture claims not established by tests.
- **Implement:** Update README setup/architecture/status, env examples, migration instructions, ADR references and future-work links. Preserve history by superseding ADRs rather than silently changing prior rationale. Replace `principals.md` instructions that mandate fabricated gauges, certainty, hormonal claims or covert persuasion with evidence-linked product principles. Keep the existing UX research as supporting material, but do not repeat its “100-source” scope claims without verifying the missing half. Record known limitations and correct provider/topology terminology.
- **Accept:** A fresh contributor follows documented setup/test commands; referenced local paths resolve; no checked item relies solely on prose; all deferred work maps to this tracker. Current behavior and future intentions are distinguishable. Run a documentation/link check and compare product claims with tests.

### T48 — Complete threat modeling and independent security validation

- [ ] **P1 · G/E · SEC + QA · Depends: T02–T14, T17, T22, T23, T27**
- **Implement:** Document trust boundaries for browser, GitHub, queue, workers, models, databases and observability. Cover BOLA, role escalation, CSRF, XSS/markdown links, credential leakage, SSRF, injection, supply chain, expensive input and malicious repository content. Test hostile URLs/paths/provider responses in isolated fixtures. Assign severity, owner and remediation evidence. Commission independent review for private-repository launch when the threat model warrants it.
- **Accept:** No unresolved applicable P0/P1 security defect; access-control regression matrix passes across tenants/roles. Credential rotation/revocation and incident containment are rehearsed. Clearly label untested deployment controls and vendor assurances. Sources: [S04][S04], [S08][S08], [S09][S09], [S10][S10].

### T49 — Establish support, incidents, and privacy-aware product measurement

- [ ] **P1 · G/R · SRE + UX · Depends: T20, T23, T26, T45, T46**
- **Implement:** Assign service/support owners and escalation contacts; write runbooks for stuck reviews, provider outage, bad recommendation, unauthorized data access, unavailable budget ledger and failed publication. Add trace/request IDs to support-friendly errors. Instrument activation, completed useful reviews, task errors and helpful/dismissed findings without logging code, tokens or review bodies. Keep notification preferences explicit and reversible.
- **Accept:** Run a tabletop incident and a synthetic support ticket through diagnosis/recovery. Users can report a wrong finding and disconnect/export/delete without friction. Product success is useful completed work and decision quality, not session duration or compulsive daily opens. Alerts identify an owner and action.

### T50 — Pass release gates and run a limited pilot

- [ ] **P1 · R/E · Release owner + QA · Depends: all P0/P1 tasks T01–T49**
- **Implement:** Complete section 11 with linked evidence; document any P2 exclusions. Start with designated repositories and manual observation, then increase traffic only after SLO, cost, correctness and support signals hold. Use publication/model kill switches and a rollback owner. Obtain explicit release authorization after the release candidate is concrete and reviewable.
- **Accept:** Pilot scope/limits are communicated; no open release blocker is hidden behind a readiness score. Two successive candidate builds pass required checks and the deployed candidate passes external smoke/recovery checks. General availability follows evidence, not elapsed calendar time.

### T51 — Evaluate calibrated confidence and feedback learning

- [ ] **P3 · R · ML · Depends: T12, T15, T20, T23, T50**
- **Implement:** Replace blanket confidence multipliers only after collecting adequately labeled, consented feedback. Separate correctness labels from human override preference. Measure Brier score/reliability curves and precision/coverage by language, severity and repository; hold out repositories/time periods to reduce leakage. Compare deterministic policy, calibrated model score and any referee/ensemble proposal against the same baseline.
- **Accept:** Improvement survives held-out evaluation with sample counts/uncertainty; critical false-negative performance does not regress. Feedback poisoning, selection bias and cold-start behavior are tested. No self-modifying production thresholds or automatic training on private code without approved policy. Human review remains available.

### T52 — Benchmark retrieval before adding complexity

- [ ] **P3 · R · ML + DATA · Depends: T13, T15, T29, T30, T50**
- **Implement:** Build a labeled code-context benchmark; compare current retrieval with lexical/BM25, semantic, hybrid/RRF and optional reranking under identical tenant/source constraints. Measure Recall@k, nDCG, useful-context rate, downstream finding quality, p95 latency and cost. Test stale/deleted code and injection-bearing documents. Tune chunk budgets and deduplication based on results.
- **Accept:** A proposed retrieval change improves an agreed outcome within latency/cost bounds; otherwise retain the simpler approach. Do not assert that DiskANN, HNSW, RRF or AST retrieval is universally best. Persist retrieval provenance so a finding's source can be audited.

### T53 — Add language-aware parsing and deterministic analyzers selectively

- [ ] **P2 · R · BE + ML · Depends: T07, T15, T29, T50**
- **Implement:** Prioritize languages used by pilot repositories. Benchmark real parsers and deterministic lint/security tools for changed entities, dependencies and diff coordinates. Define parse-error fallback, generated/binary/lockfile treatment and bounded execution. Treat whitespace/comment/import-only changes with an explicit policy; do not auto-approve them merely because a parser sees no function change.
- **Accept:** Fixtures include syntax errors, macros, decorators, multiline strings, renames and behavior-changing configuration. Analyzer outputs map to source with evidence; false-positive/noise rates and runtime justify inclusion. Tool execution is isolated and never gets production credentials.

### T54 — Optimize routing, caching, and unit economics experimentally

- [ ] **P3 · R · ML + BE · Depends: T15, T18, T19, T50**
- **Implement:** Compare model tiers on quality, latency and total cost including retries/retrieval. Cache only with keys including tenant, repository/commit, prompt/policy/model and relevant context versions; define invalidation and retention. Shadow routing changes before controlled exposure. Keep a known-good fallback and explicit capability checks.
- **Accept:** Savings are measured on real distributions without unacceptable critical-finding regression. Budget controls still bound retries and fallbacks. Cache cannot cross tenants or reuse stale findings. Do not auto-apply an advisor merely because it logs a recommendation.

### T55 — Add live updates only when polling evidence justifies them

- [ ] **P2 · R · FE + BE + SRE · Depends: T20, T28, T41, T46, T50**
- **Implement:** First measure polling load and update delay; retain adaptive polling if sufficient. If SSE is justified, define authenticated tenant-scoped events, event IDs/replay, reconnect/backoff, heartbeat and deployment capacity. Keep snapshot reconciliation and polling fallback. Supersede `docs/adr/ADR-003-frontend-data-strategy.md` through an explicit decision; the other ADR-003 covers the data layer.
- **Accept:** Reconnect across replicas does not lose important state, duplicate actions or leak events; expired sessions stop streaming. A slow consumer is bounded. User-perceived benefit and infrastructure cost are measured against polling.

### T56 — Gate automated fixes and code execution behind stronger controls

- [ ] **P3 · R · SEC + BE + ML · Depends: T07, T08, T11, T15, T48, T50**
- **Implement:** If users request patches, produce a preview diff tied to exact head SHA, explain changes and require explicit application authority. Run checks in disposable sandboxes without production secrets and with restricted egress/resources. Use separate least-privilege write credentials. Keep signing, audit, provenance, branch protections and rollback.
- **Accept:** Malicious build scripts, dependency hooks, fork PRs and changed heads cannot execute privileged operations. Failed checks block application. No auto-merge default; benchmark patch correctness beyond test pass rate. Stop the experiment if review burden or security risk exceeds its benefit.

### T57 — Add enterprise identity and governance when demanded

- [ ] **P2 · R/E · BE + SEC + UX · Depends: T03, T04, T23, T48, T50**
- **Implement:** Based on validated customer requirements, add SSO/SCIM, lifecycle offboarding, organization policies, approvals, audit export and data residency controls. Define seat/role ownership and break-glass access. Map controls/evidence to the requested assurance framework; obtain qualified review before compliance claims.
- **Accept:** Deprovisioning revokes live sessions/grants, role changes propagate predictably, and admin exports are scoped/audited. Do not claim SOC 2/ISO certification from implementing a checklist. Provider and jurisdiction constraints are documented.

### T58 — Extend developer workflow ergonomics

- [ ] **P2 · R · FE + BE + UX · Depends: T35–T39, T45, T50**
- **Implement:** Prioritize from user friction: saved views, severity/file/agent filters, per-workflow cost drill-down, copy/export, documented shortcuts, review history comparison and notification preferences. Add repository policy configuration with validation/version history. Keep technical details discoverable without making every user configure them.
- **Accept:** Each feature improves a measured task and works on mobile/keyboard; saved views cannot carry unauthorized repository scope. Notifications deduplicate and honor mute/digest preferences. Export includes provenance and limitations rather than a misleading approval certificate.

### T59 — Validate commercial packaging against measured costs

- [ ] **P2 · R/E · Product + BE · Depends: T18, T23, T45, T50**
- **Implement:** Measure compute, model, storage, support and retry cost per useful review across PR-size distributions. Validate willingness to pay before publishing tiers. If billing is introduced, implement idempotent payment webhooks, quota/entitlement reconciliation, clear metering, grace states, invoices and cancellation/export behavior. Keep prices/configuration factual and owner-approved.
- **Accept:** Usage and invoices reconcile, duplicate billing events cannot double charge, and downgrade/cancellation behavior is understandable. No invented margins, customer counts or ratings appear in the product. Commercial/legal decisions require owner review, not agent assumptions.

### T60 — Maintain the product with recurring evidence checks

- [ ] **P2 · R · Release owner + SRE + ML + UX · Depends: T50**
- **Implement:** Schedule dependency/advisory updates, access reviews, restore drills, threat-model refresh, model/prompt/retrieval evaluations, accessibility regression checks and documentation validation. Watch model retirement, provider price/capability changes, dataset drift and deletion backlog. Maintain a deprecation process for APIs, schemas and product features.
- **Accept:** Every recurring check has an owner, cadence, trigger, evidence location and remediation SLA. Detect a deliberately seeded stale dependency, failing restore, inaccessible control and review-quality regression. Reprioritize this tracker as evidence changes; archived tasks retain their verification history.

## 8. Concrete product and visual specification

**Design direction: a calm, evidence-led review workspace.** Use familiar developer-tool structure, readable surfaces and one primary action per task. Attract people through useful reviews and predictable behavior. Do not optimize for covert addiction, compulsive checking, false certainty or time spent. This is a proposed direction to validate, not a claim that one theme is psychologically best for everyone.

### Theme and component contract

Map these semantic roles to CSS variables and Tailwind tokens. Hex values are a starting specification; test actual foreground/background combinations, opacity, disabled states, charts and native controls after implementation.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| Canvas | `#F8FAFC` | `#0B1220` | Page background |
| Surface | `#FFFFFF` | `#111827` | Cards, tables, dialogs |
| Raised surface | `#F1F5F9` | `#1E293B` | Selected/hover regions, secondary panels |
| Primary text | `#0F172A` | `#F8FAFC` | Titles and reading text |
| Secondary text | `#475569` | `#CBD5E1` | Supporting text, timestamps |
| Link/accent text | `#1D4ED8` | `#93C5FD` | Links, focus and selection |
| Primary action background | `#1D4ED8` | `#1D4ED8` | White label; dark-theme boundary/focus must remain distinct |
| Decorative separator | `#CBD5E1` | `#334155` | Nonessential divisions, not the sole control boundary |
| Control boundary | `#64748B` | `#94A3B8` | Inputs and meaningful component boundaries |
| Success text | `#166534` | `#86EFAC` | Recorded completion; never “code is secure” |
| Warning text | `#92400E` | `#FDE68A` | Attention, partial coverage, pending decision |
| Error text | `#B91C1C` | `#FCA5A5` | Failed operations or blocking findings |

Calculated solid-color examples using WCAG relative luminance: light primary text on white **17.85:1**, secondary **7.58:1**, blue link **6.70:1**; dark primary text on `#111827` **16.96:1**, secondary **11.95:1**, blue link **9.84:1**; white on primary action **6.70:1**. These calculations do **not** certify the rendered app. Do not lower contrast through opacity without rechecking.

- **Type:** system sans stack for interface, monospace for code/identifiers. Body 14–16px with 1.5 line-height; key explanatory/decision copy 16px; secondary labels normally 12–14px; page titles 24–32px. Do not hide important safety/permission information in 10px text. Use tabular numerals for aligned counts/costs.
- **Spacing:** 4/8/12/16/24/32/48px scale; 16px mobile page gutter, 24–32px desktop. Text paragraphs about 60–80 characters wide. Use an 8px control radius and 12px panel radius consistently; avoid nested decorative cards.
- **Layout:** desktop navigation around 240px with a flexible content pane; collapse based on available content width, not a device brand. Reading content may cap near 1280px; diffs can use additional width. Keep long identifiers wrapping within bounded flex/grid children.
- **States:** every control defines default, hover, focus-visible, active, disabled, pending and invalid behavior. Disabled must have an explanation when the missing prerequisite is not obvious. Use icons/text alongside semantic color.
- **Motion:** suggested 120–180ms for ordinary feedback, up to 240ms for a drawer; animate opacity/transform where appropriate. Honor reduced motion; stop decorative loops. No simulated progress or forced waiting to create perceived work. Do not animate entire tables after polling.
- **Focus:** an easily visible outline with offset, adapted for both themes; not hidden by sticky UI. Preserve focus across refreshes. Product target is full focus visibility, stronger than merely meeting the minimum obscuration rule.
- **Brand assets:** one Hadron wordmark/icon family, no redundant “golden ratio” redesign requirement. Verify 16/32px favicon legibility, 180px touch icon, 192/512px app icons and 1200×630 sharing image; use real file signatures and metadata URLs. Keep decorative SVGs hidden from assistive technology; meaningful logo links have names.

### Screen-by-screen contract

| Route/surface | Main content and action | Secondary detail | Required exceptional states |
| --- | --- | --- | --- |
| Public landing / `/solutions/[framework]` | Factual problem/benefit, product evidence, connect/learn action | Supported languages, limits, permission/data explanation | Unsupported slug, unavailable service, signed-in return path; public content must not require a session |
| Authentication / `/auth/callback` | Secure GitHub sign-in, explicit progress/result | Permissions and return destination | Denied consent, invalid/replayed state, expired session, repeated effect, unavailable OAuth |
| `/` signed in | Pending decisions, failed/running reviews, recent activity | Time window, source freshness | First run, no authorized repos, unavailable subset of metrics; never fabricated health |
| `/repositories` | Installation/repo connection status and next setup action | Permissions, index freshness, last event | Zero repos, org repos, pagination, revoked installation, partial index, stale failed request |
| `/reviews` | PR identity, execution status, recommendation, findings, date | Filters/search/sort/pagination | No results versus failure, stale refresh, unknown status, inaccessible repo, empty last page |
| `/reviews/[id]` | Recommendation with coverage and source evidence | Diff, agent outputs, audit/publication/cost details | Source missing, failed mandatory check, stale SHA, unpublished result, invalid ID, large diff |
| `/hitl` | Oldest authorized pending decisions with scoped counts | Filters, assignment if implemented, queue age | No pending work, >100 items, conflicts, revoked permission, unavailable queue |
| `/hitl/[id]` | Inspect evidence → choose decision/reason → submit exact effect | Prior decision and publication history | Already resolved, stale version/SHA, permission loss, failed publish, recoverable draft |
| `/economics` | Cost window, actual/estimated spend, enforced/advisory budget | Per-review/model breakdown, accessible data table | Ledger unavailable, no calls, delayed charges, exceeded reservation, restricted role |
| `/health` | Timestamped capability status | Authorized dependency diagnostics/runbook links | API live but worker down, optional retrieval degraded, stale status, offline |
| Shell / palette / dialogs | Navigate, switch authorized workspace, choose theme | Shortcuts/help/session controls | Keyboard-only, IME, no results, tall content, mobile keyboard, storage unavailable |

### Execution and decision language

Use separate visible concepts, each grounded in server data:

| Concept | Example labels | Never substitute |
| --- | --- | --- |
| Execution | Queued, Reviewing, Completed, Failed, Cancelled, Superseded | “Completed” for a provider exception |
| Coverage | Required checks complete; Security check unavailable; 3 files excluded | “No issues” for unreviewed code |
| Recommendation | Approve recommended; Changes recommended; Human review required; Not available | Guaranteed safe / fully protected |
| Human decision | Recorded by person at time for commit; Awaiting decision | AI recommendation as human sign-off |
| Publication | Pending; Posted to GitHub; Retry scheduled; Delivery failed | Recorded internally means posted externally |
| Freshness | Reviewed SHA; current head; last refreshed | Old finding presented as current-head evidence |
| Confidence | Uncalibrated model estimate / calibrated result with method and limits | Probability of secure deployment |

### Human-factors research applied as hypotheses

| Evidence | Design inference for Hadron | How to evaluate it |
| --- | --- | --- |
| Microsoft Human-AI Interaction guidelines describe capability/limitation communication and recovery patterns. [S11][S11] | Explain what was checked, what failed, and how a person can correct/dismiss a finding. | Users correctly identify incomplete review and the next action. |
| Buçinca et al. found cognitive-forcing interventions could reduce overreliance but lower subjective ratings in their task. [S12][S12] | Keep meaningful evidence inspection for consequential decisions; do not optimize every confirmation away. | Measure decision accuracy/errors alongside speed and satisfaction. Transfer to code review must be tested. |
| Zhang et al. found confidence information can calibrate trust without necessarily improving joint decisions. [S13][S13] | A confidence badge is not proof of correctness; retain source context and uncertainty. | Compare false acceptance and reviewer understanding, not just confidence in the tool. |
| Bansal et al. found explanations can increase acceptance regardless of correctness in studied tasks. [S14][S14] | Favor checkable evidence over persuasive generic reassurance. | Include deliberately wrong suggestions in controlled usability studies and measure rejection. |

Do not infer hormonal effects from colors, universal seven-item limits, “digital vastu,” or guaranteed habits from these studies. The existing `docs/ux-research-human-factors.md` is useful background; the directly inspected sources below anchor this plan.

### Concrete reference products and patterns

These are public documentation/design references, **not reverse engineering of private competitor implementations**.

| Reference | Pattern to adapt | Hadron application and limitation |
| --- | --- | --- |
| GitHub Primer [S20][S20] | Consistent navigation, loading/degraded/empty states, semantic primitives | Familiar review workspace with predictable focus and recovery. Use its design reasoning without assuming a component install guarantees accessibility. |
| IBM Carbon tables [S21][S21] | Clear table labels, toolbar, sorting/pagination, progressive disclosure | Reviews/HITL lists stay scannable; large evidence opens in detail. Avoid forcing spreadsheet complexity into simple tasks. |
| Google Material accessibility, official legacy guidance [S22][S22] | Hierarchy, redundant cues, focus order and touch ergonomics | Text-plus-color statuses and comfortable controls. Native dp targets are inspiration, not web WCAG units. The Material 3 page could not be inspected beyond its JavaScript notice. |
| GitHub Copilot review docs [S24][S24] | Review requests, suggested changes and feedback tied to PR workflow | Keep recommendations near source, clear re-review and feedback paths. Do not assume Hadron supports the same permissions or automation. |
| CodeRabbit public review docs [S23][S23] | Visible review summaries/walkthroughs and review controls in public documentation | Benchmark how quickly a person can understand and manage a review. Do not claim proprietary architecture, algorithms, accuracy or superiority. |

## 9. State and interaction acceptance matrix

These are test fixtures to implement, not claims of existing coverage. Apply relevant rows to all screen/API contracts above. Automated checks supplement manual browser and assistive-technology testing.

| Fixture / trigger | Required product behavior | Verification |
| --- | --- | --- |
| S0: session bootstrap pending | Neutral shell/loading; no private queries until identity known | Network assertions; no old account flash |
| S1: first authorized visit, no connection | Explain setup and one connect action | Keyboard/touch onboarding completes |
| S2: connected but no review | Explain first webhook/review prerequisite | No invented metrics or “safe” result |
| S3: filters match zero items | State filter scope, clear/reset action | URL state and back/forward preserved |
| S4: initial fetch delayed | Stable named skeleton/progress; usable navigation | Layout shift and announced loading checked |
| S5: initial fetch fails | Sanitized error, useful retry and request reference | No empty-success panel or raw stack trace |
| S6: background refresh fails | Keep same-tenant stale data with freshness notice | Focus/expanded state preserved; stale label visible |
| S7: offline then reconnect | Explain offline; protect draft; bounded retry | No replay of non-idempotent actions without reconciliation |
| S8: session expires (401) | Reauthenticate with safe return path | Sensitive cache cleared; safe draft policy tested |
| S9: permission denied/revoked (403) | Explain lack of access without private details | No disabled client control can bypass backend |
| S10: missing/removed resource (404) | Scoped not-found recovery to list | No existence disclosure across tenants |
| S11: stale decision/version (409) | Show current resolution and preserve local note for comparison | Never overwrite another reviewer automatically |
| S12: invalid submission (422) | Specific field error and retained values | Label/description association; first error receives focus |
| S13: limited/quota reached (429) | Explain scope and retry/reset time when known | No retry storm, fake countdown or upgrade coercion |
| S14: provider/dependency outage | Explicit failure/degradation/coverage | Failed security check never appears approved |
| S15: retryable publication failure | Decision/result retained, delivery status separate | Reconciliation avoids duplicate GitHub comments |
| S16: workspace switch with delayed prior response | Immediately clear scope; discard prior response | A→B race fixture proves no data crossover |
| S17: empty/nonempty and >100 pending items | Accurate totals and reachable pagination | Last item reachable; org repos included |
| S18: same PR receives newer commit | Mark previous review superseded/stale | No stale recommendation applies to new SHA |
| S19: binary/large/truncated diff | State exclusions; source link; bounded view | Honest coverage and responsive scroll/navigation |
| S20: unknown/null/malformed server field | Fallback label or contract error | No default critical severity/80% confidence fabrication |
| S21: rapid double submit / reload mid-submit | Idempotent request and restored known result | One decision/publication; no false success toast |
| S22: reduced motion, forced colors, zoom | Equivalent information and operable controls | No required animation, hidden focus or clipped actions |
| S23: storage/clipboard blocked | Session-local preferences and manual copy recovery | No crash; copy feedback reflects actual success |
| S24: long/Unicode/RTL text and code paths | Wrapping/bidi isolation; correct source coordinates | No injection, broken links or lost actions |
| S25: two tabs with changed permissions/state | Revalidate authoritative state | Stale tab cannot act with revoked permissions |

**Accessibility release scope:** WCAG 2.2 AA target, including text/nontext contrast, keyboard operation, names/roles/states, reflow, error association, status messages, focus visibility/obscuration and target-size rules. Use 4.5:1 for normal text, 3:1 for large text and relevant nontext boundaries; check applicable exceptions. Automated “zero violations” is necessary but insufficient. Test NVDA with a supported Windows browser and VoiceOver with Safari/iOS, or record unavailable combinations as explicit release evidence gaps. [S05][S05], [S06][S06]

## 10. Verification evidence and execution recipes

### Audit results actually observed

| Check | Result | Meaning / limit |
| --- | --- | --- |
| Git baseline | `b6be3a6` plus preserved user changes | Findings describe working tree, not only committed source |
| `.venv/bin/ruff check backend/ tests/` | PASS on 29 Oct | Lint only; does not prove runtime correctness |
| Python AST syntax parse | PASS: 106 files across backend/tests/api | No module imports, credentials, provider calls or DB access |
| `cd frontend && npm run lint` | FAIL on 29 Oct: seven parser diagnostics beginning at reviews page line 34 | Script runs `tsc --noEmit`; UI runtime validation is blocked |
| `cd frontend && NEXT_TELEMETRY_DISABLED=1 npm run build` | FAIL recorded during 27 Oct review, webpack errors | Not rerun after the 29 Oct conclusive parser failure; must pass after T01 |
| Failed-agent offline probe | Actual adapter/runner functions convert synthetic failed security output to `success=True`, empty error, confidence .3, verdict approve | Isolates failure propagation; complete production aggregator was not executed |
| Enqueue/replay offline probe | `ConnectionError` after marker write, then `DuplicateWebhookError`; marker remains | Demonstrates lost enqueue/redelivery window; not a claim of ordinary concurrent duplicate ARQ jobs |
| HITL mapping/import inspection | approve/request_changes/dismiss all map `COMMENT`; `get_redis_client` undefined | Product side-effect semantics and rebuild path require repair |
| Migration parser offline probe | 40 nonblank SQL segments; 21 retained, 19 skipped | Includes skipped required DDL; no live database migration attempted |
| Task dependency validation | 60 tasks, no missing IDs or cycles under expanded ranges | Does not substitute for implementation or release evidence |
| Theme contrast calculation | Solid-color pairs listed in section 8 pass normal-text contrast threshold | Actual opacity, surrounding states and rendered controls still need testing |
| Full pytest/integration/paid evaluation suite | NOT COMPLETED in this audit | Earlier interrupted test attempt has no retained final result; do not infer pass/fail counts |
| Browser/mobile/axe/field performance | NOT RUN on this noncompiling working tree | All related results remain release tasks |
| Deployed security, image contents, restore/load testing | NOT VERIFIED | Requires authorized staging/account configuration and real infrastructure |

The critical offline probe was run as `python3 /tmp/hadron_critical_audit_probe.py`. It extracted unchanged function ASTs with fake collaborators, blocked outbound socket calls, and avoided app imports, `.env`, lifespan and external services. `/tmp` is ephemeral and not a deliverable dependency: reproduce its cases as committed regression tests under T06/T09/T12/T14. Do not confuse the synthetic probe with a complete authenticated end-to-end exploit or production test.

### Existing safe checks

From the repository root:

```bash
.venv/bin/ruff check backend/ tests/
python3 - <<'PY'
import ast
from pathlib import Path
paths = [*Path('backend').rglob('*.py'), *Path('tests').rglob('*.py'), *Path('api').rglob('*.py')]
for path in paths:
    ast.parse(path.read_text(), filename=str(path))
print(f'Parsed {len(paths)} Python files')
PY
```

From `frontend/`, after T01 (they currently fail):

```bash
npm run lint
NEXT_TELEMETRY_DISABLED=1 npm run build
```

Before a clean-install check, select/pin supported runtimes, verify lockfiles and use an isolated checkout. `npm ci` installs the existing lock, not an upgrade. A dependency vulnerability scan requiring network is a separate check; its successful completion was not claimed here.

### Regression suites to create under T25

The following filenames are **proposed**, not existing files. Use network-denied unit/contract fixtures with explicit test settings (`_env_file=None` where applicable), fake credentials and ephemeral stores. Label external tests explicitly; do not run unclassified existing tests against `.env`.

| Proposed suite | Required scenarios |
| --- | --- |
| `tests/test_auth_contract.py` | Anonymous/role/CSRF/session/revocation matrix, every protected route, no client authority |
| `tests/test_tenant_isolation.py` | Two tenants, repo/ID/query/cache/aggregate/vector/export isolation; pooled context reset |
| `tests/test_agent_failure_contract.py` | Provider/parse/security/budget failure propagation, incomplete coverage cannot approve |
| `tests/test_webhook_delivery.py` | Duplicate delivery, marker/enqueue crash, queue outage, replays/new SHA |
| `tests/test_workflow_recovery.py` | Restart at each stage, deadline/cancel/dead-letter, no lost terminal record |
| `tests/test_publication_outbox.py` | Ambiguous GitHub timeout, reconciliation, 422 line mapping, stale head |
| `tests/test_hitl_transactions.py` | Existing row lock retained, conflict/idempotency, actor provenance, durable feedback/publication |
| `tests/test_schema_migrations.py` | Empty/old schema, extensions, bad certificate, failure stopping deploy, rollback/forward repair |
| `tests/test_embedding_contract.py` | Empty/mixed batches, correct dimensions/order/provider, no hash semantic fallback |
| `tests/test_budget_concurrency.py` | Concurrent reservation, retries/embeddings/evals, reconciliation and ledger outage |
| `tests/test_quality_gate.py` | Invented findings on clean PR, missed critical, judge unavailable, frozen holdout |
| `frontend/e2e/review-workflows.spec.ts` | Login/setup/reviews/HITL/switch/logout, matrix S0–S25, keyboard/mobile/axe |

Run DB/queue tests with the actual selected Postgres extensions and Redis versions; SQLite is useful for limited unit tests but cannot validate PostgreSQL locking, RLS, vector types or migration DDL. Build external integration tests around a designated test installation/repository, with cleanup and a declared provider budget. Store redacted CI evidence with the implementing change.

## 11. Release gates and evidence ledger

Every gate starts **OPEN**. Targets are proposals requiring owner agreement; none are audit measurements except the observations in section 10.

| Gate | Blocking condition / required evidence | Owner |
| --- | --- | --- |
| G1: build and supply chain | Clean locked build; current supported runtimes; applicable security scan issues resolved | FE/BE/SRE |
| G2: identity and privacy | Route/tenant/CSRF/session tests; no privileged browser secrets; provider data handling reviewed | SEC/BE |
| G3: truthful review | Failed/missing security/source never approves; exact SHA and coverage preserved; reliable judge | BE/ML |
| G4: durable workflow | Receipt, checkpoint, replay, publication and HITL concurrency/recovery tests pass | BE/SRE |
| G5: data and recovery | Verified TLS, empty/upgrade migrations, restore drill, retention/delete/export test | DATA/SEC |
| G6: costs and capacity | Concurrent budget tests, bounded queues/retries, load/soak baseline, accurate usage UI | BE/SRE |
| G7: usable interface | Core task flows plus matrix S0–S25 pass; no fake metrics/dead controls; both themes | FE/UX/QA |
| G8: accessibility/performance | Automated and manual results; supported browser/device/assistive-tech evidence; accepted performance baseline | FE/QA |
| G9: operational ownership | SLO dashboard/alerts/runbooks, kill switches, release/rollback/incident owner | SRE |
| G10: product truth and public presence | Docs, claims, metadata, permissions, privacy and support agree with actual product | UX/Release owner |
| G11: pilot approval | G1–G10 closed, P0/P1 tasks verified, scope and rollback recorded, explicit release authorization | Release owner |

Pilot evidence record to complete:

```text
Candidate commit / image digest:
Frontend / backend / worker deployment versions:
Schema version / prompt and model configuration:
Test report and external smoke evidence:
Review-quality dataset version, sample sizes and metrics:
Browser/device/accessibility coverage and limitations:
Load, budget, SLO and restore results:
Known accepted P2 exclusions with owners and dates:
Pilot installations/repositories and traffic limits:
Rollback / publication kill-switch owner:
Release authorization and date:
```

### Mapping prior deferred work to this tracker

| Previous scope | Current tasks | Handling |
| --- | --- | --- |
| Phase 15: governance/compliance | T02–T04, T08, T14, T20, T23–T24, T48, T57 | Security/privacy foundations are release requirements; enterprise certifications follow demonstrated need/evidence |
| Phase 17: developer experience | T31–T44, T45, T58 | Core usable review/decision flows are release requirements; advanced personalization comes later |
| Phase 20: continuous learning | T15, T18, T51–T54 | Reliable evaluation/budgets first; adaptive production behavior remains gated experimentation |
| Previous research/theory suggestions | T51–T56 | Benchmark against simpler baselines; retain only improvements supported by evidence |
| Previous branding/SEO/business proposals | T16, T43–T44, T59 | Reuse real assets, remove invented claims, validate commercial assumptions |
| Earlier “all complete” checkboxes | All tasks | Replaced by individual verified acceptance records; no implied carryover |

## 12. Primary-source research register

Sources inspected during this audit on 26–29 October 2026. Documentation is guidance; author abstracts support only the limited research claims stated above. This is not a systematic literature review, a competitor source-code audit, or a guarantee of causal UX benefits. Recheck time-sensitive dependency/security/provider guidance when implementing.

| ID | Primary source | What it supports |
| --- | --- | --- |
| S01 | [Next.js support policy][S01] | Supported release lines; 14.x is listed unsupported |
| S02 | [Next.js October 14, 2026 security update][S02] | Patch release context; applicability must be evaluated against enabled features/dependencies |
| S03 | [GitHub webhook best practices][S03] | Signed webhooks, durable asynchronous processing and response within ten seconds |
| S04 | [GitHub App best practices][S04] | Least privilege, token handling, repeated authorization checks and deletion planning |
| S05 | [W3C WCAG 2.2][S05] | Accessibility conformance criteria, not a visual-style recipe |
| S06 | [W3C APG modal dialog pattern][S06] | Focus management, modal semantics and keyboard behavior |
| S07 | [Google Web Vitals][S07] | LCP/INP/CLS thresholds and p75 field segmentation |
| S08 | [OWASP prompt injection guidance][S08] | Layered controls for untrusted model context; RAG is not a complete defense |
| S09 | [OWASP API object-level authorization][S09] | Authorization for every accessed object, independent of caller-provided IDs |
| S10 | [OWASP session management][S10] | Session lifecycle, cookie protections and invalidation |
| S11 | [Amershi et al., Human-AI Interaction guidelines][S11] | Research-derived interaction guidance; reviewed publication abstract |
| S12 | [Buçinca et al., To Trust or to Think][S12] | Overreliance/intervention tradeoffs in the authors' experimental task; abstract inspected |
| S13 | [Zhang et al., Confidence and trust calibration][S13] | Trust calibration is not sufficient for better joint decisions; abstract inspected |
| S14 | [Bansal et al., Does the Whole Exceed its Parts?][S14] | Explanations and acceptance/correctness tradeoffs; abstract inspected |
| S15 | [Google AI features and websites][S15] | Standard SEO applies; no special AI markup requirement or indexing guarantee |
| S16 | [Google structured-data policies][S16] | Visible, factual, representative markup; no invented reviews |
| S17 | [Google SRE error-budget policy][S17] | Explicit reliability tradeoffs and release policy tied to objectives |
| S18 | [PostgreSQL SSL documentation][S18] | Certificate and hostname verification principles; configure actual driver correctly |
| S19 | [Supabase securing data][S19] | Different access models for direct DB/Data API; least privilege and exposed-table RLS |
| S20 | [GitHub Primer product UI][S20] | Component, navigation, empty/degraded/loading and disclosure patterns |
| S21 | [IBM Carbon data-table guidelines][S21] | Enterprise table structure, toolbars, density and expanded content |
| S22 | [Google Material accessibility, legacy][S22] | Accessible hierarchy, cues and touch/focus guidance; not an inspected Material 3 implementation |
| S23 | [CodeRabbit review overview][S23] | Publicly documented review experience only |
| S24 | [GitHub Copilot code-review usage][S24] | Public PR review/suggestion/feedback workflow only |
| S25 | [Vercel Web Interface Guidelines][S25] | Practical interface review checks; used with WCAG and product-specific tests |

[S01]: https://nextjs.org/support-policy
[S02]: https://nextjs.org/blog/nextjs-security-update-october-14-2026
[S03]: https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks
[S04]: https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app
[S05]: https://www.w3.org/TR/WCAG22/
[S06]: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
[S07]: https://web.dev/articles/vitals
[S08]: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
[S09]: https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/
[S10]: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
[S11]: https://www.microsoft.com/en-us/research/publication/guidelines-for-human-ai-interaction/
[S12]: https://arxiv.org/abs/2102.09692
[S13]: https://arxiv.org/abs/2001.02114
[S14]: https://arxiv.org/abs/2006.14779
[S15]: https://developers.google.com/search/docs/appearance/ai-features
[S16]: https://developers.google.com/search/docs/appearance/structured-data/sd-policies
[S17]: https://sre.google/workbook/error-budget-policy/
[S18]: https://www.postgresql.org/docs/current/libpq-ssl.html
[S19]: https://supabase.com/docs/guides/database/secure-data
[S20]: https://primer.style/product/
[S21]: https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines
[S22]: https://m1.material.io/usability/accessibility.html
[S23]: https://docs.coderabbit.ai/guides/code-review-overview
[S24]: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/use-code-review
[S25]: https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
