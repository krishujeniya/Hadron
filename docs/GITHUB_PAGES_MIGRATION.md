# Hadron Architecture: Decoupled GitHub Pages Frontend & Vercel Backend

## 1. System Topology

Hadron employs a decoupled production hosting architecture that separates the static client interface from serverless API and persistent worker infrastructure:

```
[Browser Client]
  │
  ├─► GitHub Pages: https://krishujeniya.github.io/Hadron/
  │     - Static SPA bundle generated via Vite (`npm run build:pages`)
  │     - Base path `/Hadron/`
  │     - Client-side navigation via `frontend/src/compat/next/`
  │     - 404.html URL reconstruction protocol for direct links & refresh
  │
  ├─► Vercel Backend: https://hadron-backend.vercel.app/
  │     - Serverless FastAPI execution (`api/index.py` via `vercel.json`)
  │     - CORS allowlist explicitly permitting `https://krishujeniya.github.io`
  │     - Cross-origin session token and bearer authentication
  │     - Webhook ingestion from GitHub App (`/api/v1/webhooks/github`)
  │
  └─► Existing Vercel Frontend: https://hadron.vercel.app/ (Preserved)
        - Next.js server build (`npm run build`) remains intact

[Backend Infrastructure & Services]
  │
  ├── PostgreSQL + pgvector (Persistent database storage)
  └── External Worker Infrastructure (Redis + ARQ + LangGraph execution)
```

---

## 2. Cross-Origin Authentication Architecture

### The Third-Party Cookie Constraint
Modern browser privacy engines (Safari Intelligent Tracking Prevention, Chrome Privacy Sandbox, and Firefox Enhanced Tracking Protection) block cross-site cookies on cross-origin `fetch` requests between `https://krishujeniya.github.io` and `https://hadron-backend.vercel.app`. Relying solely on `Set-Cookie` fails in third-party contexts.

### The Hybrid Token + Header Protocol
Hadron implements a standards-compliant cross-origin authentication flow:

1. **OAuth Initialization**:
   - The frontend generates an OAuth state parameter and redirects to the backend `/api/v1/auth/github/login` endpoint with `redirect_uri=https://krishujeniya.github.io/Hadron/auth/callback`.
   - The state value is cached in browser `sessionStorage`.

2. **OAuth Callback & State Binding**:
   - GitHub redirects the user back to `https://krishujeniya.github.io/Hadron/auth/callback?code=...&state=...`.
   - The frontend callback handler retrieves the expected state from `sessionStorage` and attaches it to the exchange request via the `X-OAuth-State` header.
   - The backend validates the state against both the cookie and the `X-OAuth-State` header, preventing CSRF even when cross-site cookies are blocked.

3. **Session Token Issuance & Storage**:
   - Upon successful code exchange, the backend returns the authenticated `AccountProfile` containing:
     - `session_token`: An opaque high-entropy token stored server-side in the session cache.
     - `csrf_token`: A cryptographic CSRF token.
   - The response also sets `X-Hadron-Session` and `X-CSRF-Token` headers.
   - The frontend persists the session token in `localStorage` under `hadron_session_token` and CSRF token under `hadron_csrf_token`.

4. **Authenticated API Calls**:
   - All subsequent requests from the frontend client inject:
     - `Authorization: Bearer <session_token>`
     - `x-csrf-token: <csrf_token>`
   - The backend dependency `get_current_account` checks the bearer header first, falling back to session cookies when present.

---

## 3. CORS and Transport Security

The backend CORS policy in `backend/main.py` explicitly allows:
- `https://krishujeniya.github.io`
- `https://hadron.dev`
- `https://hadron.vercel.app`
- `http://localhost:3000` (Next.js local development)
- `http://localhost:5173` and `http://127.0.0.1:5173` (Vite local development)

Allowed headers include:
- `Authorization`, `Content-Type`, `X-CSRF-Token`, `X-API-Key`, `X-OAuth-State`, `Accept`.

Exposed headers include:
- `X-Hadron-Session`, `X-CSRF-Token`.

---

## 4. Static Frontend Routing & GitHub Pages 404 Protocol

GitHub Pages is a static file host that does not natively support server-side URL rewrites for single-page applications.

### Base Path Handling
All static assets, route links, and script references are anchored to `/Hadron/`:
- Vite configuration: `base: "/Hadron/"`.
- Next.js Link compatibility shim: automatically prepends `/Hadron` when deployed on GitHub Pages.
- API requests: client automatically detects hostname matching `*.github.io` and routes directly to `https://hadron-backend.vercel.app`.

### Direct Deep Links & Refresh Handling
To support direct navigation to arbitrary dynamic paths (such as `/reviews/rev_123` or `/hitl/hitl_456`):
1. When a user navigates directly or refreshes, GitHub Pages returns `frontend/public/404.html`.
2. The lightweight redirect script in `404.html` converts the request path and query into `/?p=<path>` and executes `window.location.replace()`.
3. `index.html` loads, and `frontend/src/compat/next/router-context.tsx` extracts `spaPath = searchParams.get('p')`.
4. `window.history.replaceState` restores the clean browser URL, and the client-side router mounts the requested page component without any user interruption or full page reload.

---

## 5. Dual-Build Compatibility Matrix

The repository maintains full dual-target compatibility:

| Target | Command | Output Directory | Configuration | Purpose |
|---|---|---|---|---|
| **GitHub Pages** | `npm run build:pages` | `frontend/dist/` | `frontend/vite.config.ts` | Static SPA bundle with base `/Hadron/` |
| **Vercel Frontend** | `npm run build` | `frontend/.next/` | `frontend/next.config.mjs` | Server-rendered Next.js 15 application |
| **Vercel Backend** | `vercel deploy` | Python runtime | `vercel.json` | Serverless FastAPI backend entrypoint |

---

## 6. GitHub Actions Deployment Workflow

The static deployment workflow is defined in `.github/workflows/deploy-gh-pages.yml`:
- Trigger: Push to `main` touching `frontend/**` or `.github/workflows/deploy-gh-pages.yml`.
- Permissions: `contents: read`, `pages: write`, `id-token: write`.
- Steps:
  1. Check out repository.
  2. Set up Node.js 20 with package-lock caching.
  3. Install dependencies via `npm ci`.
  4. Run TypeScript checks via `npm run lint`.
  5. Build static assets via `npm run build:pages`.
  6. Verify generated assets (`index.html`, `404.html`, `.nojekyll`, `assets/`).
  7. Deploy artifact to GitHub Pages via `actions/deploy-pages@v4`.
