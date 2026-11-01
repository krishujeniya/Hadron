# Runbook: RB-04 Unauthorized Access & Cross-Tenant Containment

## 1. Trigger & Symptom
- Security alert: Repeated HTTP 403 Forbidden spikes on `/api/v1/reviews/{id}` or `/api/v1/hitl/{id}` from a single authenticated principal.
- Log signature: `Unauthorized cross-account review read attempt` or `Unauthorized HITL decision attempt`.

## 2. Diagnosis Steps
1. Search security logs for the offending session and IP address:
   ```bash
   grep -E "Unauthorized cross-account|Permission denied" /var/log/hadron/api.log | tail -n 50
   ```
2. Identify the actor's session ID and associated GitHub user login:
   ```sql
   SELECT session_id, user_id, github_login, created_at, expires_at, is_revoked
   FROM user_sessions
   WHERE user_id = '<offending_user_id>';
   ```
3. Check if any private review or repository rows were leaked in the response payloads (confirm HTTP 403 was returned with zero data disclosure).

## 3. Remediation Procedure
1. Immediately revoke the user's active application session:
   ```sql
   UPDATE user_sessions
   SET is_revoked = true
   WHERE user_id = '<offending_user_id>';
   ```
2. Remove user from Redis session cache:
   ```bash
   redis-cli -u $REDIS_URL DEL "session:<session_id>"
   ```
3. If token compromise or automated scraping is suspected, block the source IP in WAF/Cloudflare.
4. Notify the security officer and compile an incident breach assessment if required by tenant agreements.
