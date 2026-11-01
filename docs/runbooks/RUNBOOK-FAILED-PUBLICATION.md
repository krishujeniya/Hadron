# Runbook: RB-06 Review Publication Outbox Reconciliation

## 1. Trigger & Symptom
- Review completed in PostgreSQL (`status = 'completed'`), but `github_review_id` is null or delivery status is `delivery_failed`.
- GitHub PR does not display the expected Hadron review comment.
- Alert: `github_publication_delivery_failed_total > 5`.

## 2. Diagnosis Steps
1. Find completed reviews missing GitHub review IDs:
   ```sql
   SELECT id, repo_full_name, pr_number, status, github_review_id, updated_at
   FROM pr_review_records
   WHERE status = 'completed'
     AND github_review_id IS NULL
     AND updated_at < NOW() - INTERVAL '5 minutes';
   ```
2. Check GitHub API client logs for error details (HTTP 401 token expired, HTTP 422 diff line mapping, HTTP 429 rate limit, or HTTP 5xx timeout).
3. Query GitHub directly to check if the review was posted upstream despite a client read timeout:
   ```bash
   gh api repos/:owner/:repo/pulls/:pr/reviews | grep "hadron-review:<workflow_id>"
   ```

## 3. Remediation Procedure
1. If the review was already posted upstream, reconcile the database record:
   ```sql
   UPDATE pr_review_records
   SET github_review_id = '<upstream_id>', updated_at = NOW()
   WHERE id = '<review_id>';
   ```
2. If the review was never delivered due to a transient network timeout or rate limit, re-trigger the outbox publisher:
   ```bash
   python -m backend.orchestrator.publisher --retry-review-id '<review_id>'
   ```
3. Verify that the GitHub PR displays the formatted review comment with correct workflow ID marker.
