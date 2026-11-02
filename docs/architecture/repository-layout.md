# Repository layout

Hadron has one Python application package, one Next.js application, and a persistent review worker that shares the backend package. The layout follows those boundaries. The application is small enough that separate workspace packages, a build orchestrator, or a second Python import root would add maintenance without a demonstrated benefit.

## Where code belongs

```text
Hadron/
├── api/index.py                 Vercel ASGI adapter
├── backend/                     Importable Python application and worker
│   ├── api/                     HTTP adapters and response schemas
│   ├── agents/                  Review agents and their contracts
│   ├── auth/                    Verified identities and server sessions
│   ├── database/                Persistence, models, certificates
│   ├── orchestrator/            Review workflow and state transitions
│   ├── job_queue/               ARQ execution and worker heartbeat
│   └── …                        Existing domain packages
├── frontend/
│   ├── src/app/                 Next.js routes, layouts, metadata and styles
│   ├── src/features/
│   │   ├── auth/                Account dialog and GitHub session context
│   │   ├── reviews/             Findings, diffs, verdicts and review summaries
│   │   ├── hitl/                Human decision form
│   │   ├── overview/            Workspace summaries and guidance
│   │   └── marketing/           Public landing content and pipeline illustration
│   ├── src/components/
│   │   ├── brand/               Hadron wordmark and icon
│   │   ├── layout/              Shell, command palette and theme switch
│   │   └── ui/                  Reusable controls and empty states
│   ├── src/lib/                 Shared transport, DTO types, theme and SWR setup
│   ├── tests/check-ui.mjs       Browser regression checks
│   └── public/                 Browser-served assets
├── tests/                       Python tests grouped by the behavior they verify
│   ├── agents/ api/ data/       Agents, HTTP contracts and persistence/ingestion
│   ├── economics/ evaluation/   Spend controls and evaluation quality
│   ├── frontend/                Existing Python checks of frontend source contracts
│   ├── operations/ reliability/ Deployment, recovery and failure handling
│   ├── security/ workflows/     Auth boundaries and review lifecycle
│   └── documentation/          Documentation/source reconciliation
├── fixtures/                    Shared webhook payload used by tests and demo
├── scripts/                     Executable development and operational tools
│   └── migrations/             Existing versioned database migration artifacts
├── docs/
│   ├── README.md                Documentation entrypoint
│   ├── tracker.md               Single execution tracker and release handoff
│   ├── architecture/ adr/       Architecture explanations and decision records
│   ├── design/ product/         Design rules, design system and roadmap
│   ├── operations/ runbooks/    Deployment, capacity, recovery and incident response
│   ├── security/               Threat model and data inventory
│   ├── research/ reviews/      Source research and historical assessments
│   └── verification/           Dated verification output and screenshots
└── .github/workflows/           CI and manual production readiness checks
```

The abbreviated tree shows responsibilities, not every backend package. The tracked tree is the authority for filenames. Root Docker/Compose files, Python manifests, npm manifests and Vercel entrypoints stay where their tools and deployment configurations expect them.

## Dependency direction

Routes compose features and shared components. A feature may use shared controls, brand elements, API transport and shared DTOs. Authentication context belongs to the authentication feature because it governs account state across routes. Shared `ui` and `brand` components must not import product features. `layout` composes features, so the shell may import the account dialog. Avoid feature-wide barrel exports: import the file that owns the behavior.

Keep Python imports under `backend`. Tests are selected by domain path and named after behavior; old phase/task IDs remain in their historical descriptions where useful. A test's directory does not imply it is a live integration test. The `eval` marker identifies the paid test; `-m "not eval"` excludes it. Browser tests live with the frontend they exercise.

Add a new shared package only when independently consumed or independently deployed code warrants it. Do not duplicate a component into multiple features to satisfy folder symmetry. Do not move generated builds, environments, provider credentials, or ignored agent state into application source.

## Research checked on 2 November 2026

These are direct inspections of upstream repositories, not starter templates. A public contribution history establishes a maintained open-source project; it cannot establish that every line was written without AI assistance. No third-party implementation code was copied.

| Source pinned at inspected commit | Observed structure | Applied decision |
| --- | --- | --- |
| [Sentry, 063a6cb](https://github.com/getsentry/sentry/tree/063a6cb279fc42752e31ee200331f553f35ec26f) | `src`, `static/app`, `tests/sentry` organized into domain directories, root tooling and lockfiles | Group tests by domain and retain explicit tooling/entrypoints. Sentry's much larger build system is not required here. |
| [Langfuse, 8ee97c4](https://github.com/langfuse/langfuse/tree/8ee97c448b232a220ce7a8049482132b606208e3/web/src) | `web/src/app`, `web/src/features`, `web/src/components`; root `worker` and `packages` | Separate product features from shared frontend components. Hadron's Python worker continues sharing the existing backend package. |
| [FastAPI, 45cb225](https://github.com/fastapi/fastapi/tree/45cb2252c737906f37544f5ba6bee0295fb81468) | An importable application/library package alongside `tests`, `scripts`, `docs`, `pyproject.toml`, `uv.lock` | Preserve the existing Python package/import root instead of introducing an unnecessary second source tree. |
| [Next.js project organization](https://nextjs.org/docs/app/getting-started/project-structure) | Framework conventions for `app`, optional `src`, `public`; organization outside route files is flexible | Preserve route filenames/URLs and asset placement; group imported feature code outside `app`. The inspected guide is current; the framework remains on the existing supported 15.x line. |

The feature and test boundaries are a Hadron-specific design choice supported by these examples. There is no single universal company folder structure, and no benchmark here proves a globally optimal arrangement. The relevant checks are discoverability, ownership, import integrity, unchanged runtime behavior and deployment compatibility.

Machine-readable upstream root and nested tree observations are in [the research evidence](../verification/structure-research-2026-11-02.json). The exact old-to-new mapping is in [the move manifest](../verification/structure-moves-2026-11-02.json).

## Verification and recovery

Run `python3 scripts/check_structure.py`, the Python suite, TypeScript check, production build and frontend browser regressions. The structure checker verifies moved destinations, removal of old source locations, frontend alias resolution and the shared component boundary. It runs in CI.

The move manifest records hashes of current working-tree files, including prior uncommitted fixes. A machine-local baseline was saved before relocation for this session. Do not use `git reset` or checkout the committed versions to undo this reorganization: doing so would discard earlier fixes. Reversing a move also requires reversing imports, test paths, documentation references and CI commands. Use the manifest and review all associated changes together.
