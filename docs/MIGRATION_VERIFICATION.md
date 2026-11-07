# Hadron Migration Verification & Operational Evidence

## 1. Automated Verification Summary

| Test Category | Command / Harness | Evidence & Status |
|---|---|---|
| **Python Backend Tests** | `.venv/bin/pytest tests/` | **421 PASSED**, 1 skipped (eval gate). All security, auth, RBAC, workflows, and data tests pass. |
| **Python Tool Sandbox** | `.venv/bin/pytest tests/agents/test_tool_registry_and_sandbox.py` | **16 PASSED** in 2.56s. Sandbox execution, syntax checks, and capability boundaries verified. |
| **Structure & Boundaries** | `python3 scripts/check_structure.py` | **PASS**. 91 component moves, frontend import contracts, and shared boundaries verified. |
| **Frontend Typecheck** | `npm run lint --prefix frontend` (`tsc --noEmit`) | **0 ERRORS**. Full TypeScript check passed cleanly across all components and shims. |
| **Static Build Pipeline** | `npm run build:pages --prefix frontend` (`vite build`) | **PASS**. Generated static bundle in `frontend/dist/` with base path `/Hadron/` in 4.12s. |
| **Next.js Production Build** | `npm run build --prefix frontend` (`next build`) | **PASS**. Compiled 19 routes successfully; ensures `hadron.vercel.app` remains intact. |
| **Playwright UI Regression** | `PLAYWRIGHT_CHROME_PATH=/usr/bin/google-chrome npm run test:ui` | **9/9 PASSED**. Responsive layouts, sign-in focus trap, dark theme, and OAuth callback exchange verified. |

---

## 2. Playwright UI Suite Test Output

```
Server ready on port 3100
> ai-pr-review-frontend@0.1.0 test:ui
> node tests/check-ui.mjs

shared sign-in, forged-storage rejection, focus trap and overflow at 375px: PASS
shared sign-in, forged-storage rejection, focus trap and overflow at 768px: PASS
shared sign-in, forged-storage rejection, focus trap and overflow at 1280px: PASS
single dashboard with legacy executive preference and session reload: PASS
single dashboard with legacy developer preference and session reload: PASS
authenticated desktop layout and overflow: PASS
public dark theme, readable review example, no ambient particle canvas: PASS
OAuth callback exchanges code once and opens dashboard: PASS
API outage shows unavailable state without false healthy status: PASS
```

---

## 3. Static Bundle Verification Evidence

The static production artifact in `frontend/dist` contains all required files for GitHub Pages:
- `index.html`: Entrypoint with preloaded modules, dark mode initialization, and base `/Hadron/` path references.
- `404.html`: Single-page app redirect handler preserving deep links on direct refresh.
- `.nojekyll`: Instructs GitHub Pages not to invoke Jekyll processing on static assets.
- `assets/`: Code-split CSS and JavaScript chunks.
- Favicons and icons: `favicon.svg`, `favicon-32x32.png`, `apple-touch-icon.png`, `icon-512.png`.

Static preview verified using `npx vite preview --port 4173`:
- Root URL: `http://127.0.0.1:4173/Hadron/` serves the complete application bundle with correct MIME types and zero 404s on assets.

---

## 4. Manual Verification Runbook

### Step 1: Public Landing and Navigation
1. Open `https://krishujeniya.github.io/Hadron/`.
2. Verify brand assets: Hadron logo renders in both light and dark modes.
3. Verify responsive layout across desktop and mobile screen sizes.
4. Verify navigation links: `/docs`, `/solutions/*`, and modal trigger for sign-in.

### Step 2: GitHub OAuth Sign-In (Cross-Origin)
1. Click **Sign in with GitHub**.
2. Confirm the browser initiates a redirect to `https://hadron-backend.vercel.app/api/v1/auth/github/login?redirect_uri=https://krishujeniya.github.io/Hadron/auth/callback`.
3. Complete GitHub authorization.
4. Verify redirect to `https://krishujeniya.github.io/Hadron/auth/callback?code=...&state=...`.
5. Observe the callback handler exchanging the code with header `X-OAuth-State`.
6. Confirm storage of `hadron_session_token` in `localStorage` and transition to dashboard overview.

### Step 3: Deep Link & Refresh Resiliency
1. Navigate directly to a dynamic review URL: `https://krishujeniya.github.io/Hadron/reviews/rev_sample_123`.
2. Confirm GitHub Pages serves `404.html`, which immediately redirects to `/Hadron/?p=/reviews/rev_sample_123`.
3. Confirm the application router unescapes `p` and mounts the `ReviewDetailPage` component with `params.id = rev_sample_123`.
4. Refresh the page (`Ctrl+R` / `Cmd+R`) and confirm that the state remains preserved without a blank screen.

### Step 4: Human-in-the-Loop (HITL) Decision Flow
1. Navigate to `/Hadron/hitl`.
2. Select a pending HITL review item.
3. Submit an approval or change-request decision.
4. Confirm network payload contains `Authorization: Bearer <session_token>` and `x-csrf-token: <csrf_token>`.
5. Verify response 200 OK from `https://hadron-backend.vercel.app/api/v1/hitl/decisions`.

---

## 5. Blocked Checks (Pending Live Production Credentials)

The following tests require external production environment secrets and are documented here with reproduction instructions:

### BLOCKED-01: End-to-End Live GitHub App Webhook Ingestion
- **Prerequisite**: Live GitHub App webhook secret (`GITHUB_WEBHOOK_SECRET`) and public endpoint URL configured in GitHub App settings.
- **Verification Command**:
  ```bash
  curl -X POST https://hadron-backend.vercel.app/api/v1/webhooks/github \
    -H "X-GitHub-Event: pull_request" \
    -H "X-Hub-Signature-256: sha256=<valid-hmac-signature>" \
    -d @tests/fixtures/pr_opened_event.json
  ```
- **Expected Result**: HTTP 200 with review task queued for background execution.

### BLOCKED-02: Live LLM Evaluation Gate
- **Prerequisite**: Active `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` with available quota.
- **Verification Command**:
  ```bash
  .venv/bin/pytest tests/evaluation/test_eval_gate.py -v -m "eval"
  ```
- **Expected Result**: Specialist agent reasoning benchmarks complete within acceptable cost and quality thresholds.
