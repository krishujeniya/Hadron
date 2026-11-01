# Runbook: RB-03 User Dispute on Inaccurate Finding

## 1. Trigger & Symptom
- Developer submits a dispute or flags a finding as a false positive in the review dashboard or GitHub comment.
- User ticket submitted: "Finding on PR #X is invalid / hallucination".

## 2. Diagnosis Steps
1. Locate the finding record using the review ID and finding UUID:
   ```sql
   SELECT f.id, f.agent_type, f.severity, f.summary, f.file_path, f.line_start, r.repo_full_name, r.pr_number
   FROM finding_records f
   JOIN pr_review_records r ON f.review_id = r.id
   WHERE f.id = '<finding_id>';
   ```
2. Inspect the prompt input and model response recorded in the debug trace for that workflow ID.
3. Determine whether the finding stemmed from:
   - Outdated code context (e.g. stale vector retrieval chunk).
   - AST parser limitation on unsupported language syntax.
   - Genuine prompt hallucination or over-sensitive security heuristic.

## 3. Remediation Procedure
1. Record human feedback in the database:
   ```sql
   INSERT INTO hitl_feedback (id, review_id, reviewer_id, is_override, override_reason, created_at)
   VALUES (gen_random_uuid(), '<review_id>', '<user_id>', true, 'Marked false positive: <explanation>', NOW());
   ```
2. If the issue is a systemic false positive affecting multiple PRs, add a suppression rule or update the specialist prompt in `backend/agents/prompts/`.
3. Respond to the user with the root cause explanation and confirm the finding will not penalize future confidence scoring.
