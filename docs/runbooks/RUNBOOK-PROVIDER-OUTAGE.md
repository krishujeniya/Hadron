# Runbook: RB-02 Upstream Provider Outage & Model Fallback

## 1. Trigger & Symptom
- Multiple consecutive LLM calls returning HTTP 500, 502, 503, or 504 from OpenAI/Anthropic.
- Circuit breaker trips in `backend/security/circuit_breaker.py`.
- Error logs indicate `LLMProviderUnavailableError` or `APITimeoutError`.

## 2. Diagnosis Steps
1. Verify upstream status pages (e.g. `status.openai.com` / `status.anthropic.com`).
2. Inspect circuit breaker metrics:
   ```bash
   curl -s http://localhost:8000/api/v1/health/circuit-breakers | jq .
   ```
3. Check error rates in review runner logs:
   ```bash
   grep -i "circuit breaker open" /var/log/hadron/worker.log | tail -n 20
   ```

## 3. Remediation Procedure
1. If the primary model is degraded, switch to the fallback provider in environment configuration:
   ```bash
   export LLM_PRIMARY_MODEL="claude-3-5-sonnet-20241022"  # or gpt-4o-mini
   docker compose restart worker
   ```
2. For in-flight reviews failing due to the outage, verify that the failure preservation contract correctly marks reviews as `escalated` or `failed` rather than falsely auto-approving.
3. Once the upstream provider resolves, reset the circuit breaker:
   ```bash
   curl -X POST http://localhost:8000/api/v1/health/circuit-breakers/reset \
     -H "Authorization: Bearer $ADMIN_SECRET"
   ```
