"use client";

import { useState } from "react";
import Link from "next/link";
import { useGitHubAccount } from "@/features/auth/github-context";
import { ParticleField } from "@/features/marketing/ParticleField";

interface SampleDiff {
  id: string;
  name: string;
  language: string;
  prTitle: string;
  repo: string;
  diff: string;
  findings: Array<{
    agent: "security" | "quality" | "test" | "docs";
    severity: "critical" | "high" | "medium" | "low";
    file: string;
    line: number;
    title: string;
    description: string;
    snippet: string;
  }>;
  verdict: "CHANGES RECOMMENDED" | "APPROVE RECOMMENDED";
  confidence: number;
}

const SAMPLE_DIFFS: SampleDiff[] = [
  {
    id: "python-sql",
    name: "Python API: SQL Injection",
    language: "Python",
    prTitle: "PR #142: Add user lookup endpoint with dynamic filtering",
    repo: "octocat/auth-service",
    diff: `@@ -42,7 +42,9 @@ async def get_user_by_filter(filter_key: str, filter_val: str, db: AsyncSession):
-    query = select(User).where(User.is_active == True)
-    return (await db.execute(query)).scalars().all()
+    # Dynamic filter query
+    raw_query = f"SELECT * FROM users WHERE is_active = true AND {filter_key} = '{filter_val}'"
+    return (await db.execute(text(raw_query))).scalars().all()`,
    findings: [
      {
        agent: "security",
        severity: "critical",
        file: "backend/api/users.py",
        line: 44,
        title: "Raw SQL query formatted with unescaped string interpolation",
        description:
          "User-controlled filter_key and filter_val are concatenated directly into raw SQL query. Allows arbitrary SQL injection and database extraction.",
        snippet: 'raw_query = f"SELECT * FROM users WHERE is_active = true AND {filter_key} = \'{filter_val}\'\\"',
      },
      {
        agent: "test",
        severity: "medium",
        file: "tests/test_users.py",
        line: 78,
        title: "Missing unit test covering malicious input characters",
        description: "New endpoint lacks test assertions verifying rejection of quotes, semicolons, and comment markers.",
        snippet: "def test_get_user_by_filter_injection(): ...",
      },
    ],
    verdict: "CHANGES RECOMMENDED",
    confidence: 0.96,
  },
  {
    id: "ts-action",
    name: "TypeScript: Missing Auth Check",
    language: "TypeScript",
    prTitle: "PR #88: Add organization invitation server action",
    repo: "acme-corp/platform-web",
    diff: `@@ -18,6 +18,11 @@ export async function inviteMember(formData: FormData) {
   const email = formData.get("email") as string;
   const role = formData.get("role") as string;
+  // Directly write invitation record to database
+  await db.invitations.create({
+    data: { email, role, invitedAt: new Date() }
+  });
+  return { success: true };
 }`,
    findings: [
      {
        agent: "security",
        severity: "high",
        file: "src/actions/members.ts",
        line: 20,
        title: "Server action mutates organization membership without session verification",
        description:
          "Endpoint can be invoked directly by unauthenticated clients without checking session cookies or organization admin permissions.",
        snippet: "export async function inviteMember(formData: FormData) {",
      },
      {
        agent: "quality",
        severity: "low",
        file: "src/actions/members.ts",
        line: 22,
        title: "Missing input email schema validation before mutation",
        description: "Email string is not validated against RFC 5322 or Zod email schema before database write.",
        snippet: 'const email = formData.get("email") as string;',
      },
    ],
    verdict: "CHANGES RECOMMENDED",
    confidence: 0.93,
  },
  {
    id: "go-race",
    name: "Go: Goroutine Map Data Race",
    language: "Go",
    prTitle: "PR #63: Parallelize metric aggregator workers",
    repo: "cloud-native/telemetry-collector",
    diff: `@@ -88,6 +88,10 @@ func (a *Aggregator) RecordBatch(metrics []Metric) {
   for _, m := range metrics {
+    go func(item Metric) {
+      a.counts[item.Name] += item.Value
+    }(m)
   }
 }`,
    findings: [
      {
        agent: "quality",
        severity: "high",
        file: "pkg/aggregator/worker.go",
        line: 90,
        title: "Concurrent write to non-thread-safe map from spawned goroutine",
        description: "Concurrent unsynchronized map mutations trigger fatal runtime panics under high request concurrency.",
        snippet: "a.counts[item.Name] += item.Value",
      },
      {
        agent: "test",
        severity: "medium",
        file: "pkg/aggregator/worker_test.go",
        line: 45,
        title: "Missing race detector execution flag in test pipeline",
        description: "Concurrency tests must be executed with -race flag to detect data races at commit time.",
        snippet: "go test -race ./pkg/aggregator/...",
      },
    ],
    verdict: "CHANGES RECOMMENDED",
    confidence: 0.95,
  },
];

export function PublicLandingPage() {
  const { openAccountModal } = useGitHubAccount();
  const [selectedDiffId, setSelectedDiffId] = useState<string>("python-sql");
  const [isRunningReview, setIsRunningReview] = useState(false);
  const [hasRun, setHasRun] = useState(true);
  const [copied, setCopied] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  const currentDiff = SAMPLE_DIFFS.find((d) => d.id === selectedDiffId) || SAMPLE_DIFFS[0];

  const handleRunReview = () => {
    setIsRunningReview(true);
    setHasRun(false);
    setTimeout(() => {
      setIsRunningReview(false);
      setHasRun(true);
    }, 450);
  };

  const handleCopyMarkdown = () => {
    const md = `## Hadron Review: ${currentDiff.prTitle}
**Verdict:** ${currentDiff.verdict} (Confidence: ${Math.round(currentDiff.confidence * 100)}%)

### Specialist Agent Findings (${currentDiff.findings.length})
${currentDiff.findings
  .map(
    (f) =>
      `* [${f.agent.toUpperCase()}][${f.severity.toUpperCase()}] **${f.title}** (${f.file}:${f.line})\n  ${f.description}`
  )
  .join("\n\n")}

---
*Reviewed by Hadron Autonomous Multi-Agent Engine*`;

    void navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="hm-site">
      {/* ------------------------------------------------------------------ */}
      {/* SECTION 1: HERO                                                    */}
      {/* ------------------------------------------------------------------ */}
      <section className="hm-hero" aria-labelledby="hadron-hero-title">
        <div className="hm-hero-copy">
          <div className="hm-eyebrow"><span className="hm-eyebrow-dot" aria-hidden="true" /> AUTONOMOUS CODE INTELLIGENCE / HADRON</div>
          <h1 id="hadron-hero-title" className="hm-headline">Every pull request deserves <span className="hm-headline-soft">a second brain.</span></h1>
          <p className="hm-lead">Meet the multi-agent review engine that thinks in parallel. Security, quality, testing and documentation specialists examine your changes, then bring the findings together for a more informed merge.</p>
          <div className="hm-actions">
            <button type="button" onClick={openAccountModal} className="hm-button">
              Connect with GitHub
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M4 12h16m-7-7 7 7-7 7" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
            <a className="hm-button hm-button-secondary" href="#demo">Explore the demo <span aria-hidden="true">↗</span></a>
          </div>
          <div className="hm-notes"><span>Built for GitHub PRs</span><span>Human review when needed</span><span>Open-source project</span></div>
          <div className="hm-hero-rail" aria-hidden="true"><span>01 / UNDERSTAND THE DIFF</span><span>02 / REVIEW IN PARALLEL</span></div>
        </div>
        <div className="hm-stage" aria-label="Illustrative multi-agent review visualization">
          <ParticleField />
          <div className="hm-stage-top"><span className="hm-window-label">HADRON / REVIEW ENGINE</span><span className="hm-status"><span className="hm-status-dot" aria-hidden="true" /> Visual concept</span></div>
          <div className="hm-window">
            <div className="hm-window-bar"><i aria-hidden="true" /><i aria-hidden="true" /><i aria-hidden="true" /><span>pull_request / illustration</span></div>
            <div className="hm-code" aria-label="Illustrative code review trace">
              <span className="hm-code-line is-muted">+  async def get_user(query):</span>
              <span className="hm-code-line">+    result = <b>await</b> db.execute(query)</span>
              <span className="hm-code-line is-muted">+    return result.first()</span>
              <span className="hm-code-line">&nbsp;</span>
              <span className="hm-code-line"><em>● security</em> / inspecting input</span>
              <span className="hm-code-line"><em>● quality</em>  / tracing context</span>
              <span className="hm-code-line"><em>● testing</em>  / checking coverage</span>
              <span className="hm-code-line"><em>● docs</em>     / reviewing changes</span>
            </div>
            <div className="hm-result"><div className="hm-result-icon" aria-hidden="true">!</div><div><strong>Potential unsafe query construction</strong><p>Illustrative finding · Surface risks with context and actionable guidance.</p></div></div>
          </div>
          <div className="hm-stage-foot"><span className="hm-mini-line" aria-hidden="true" /> An original, interactive particle environment</div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 2: PROOF METRICS                                           */}
      {/* ------------------------------------------------------------------ */}
      <section aria-label="What makes Hadron different">
        <div className="hm-capabilities">
          <div className="hm-capability">
            <span className="hm-capability-kicker">01 / Parallel intelligence</span>
            <div className="hm-capability-visual" aria-label="Four specialist review agents"><span className="hm-agent-pill">Security</span><span className="hm-agent-pill">Quality</span><span className="hm-agent-pill">Testing</span><span className="hm-agent-pill">Documentation</span></div>
            <div><h2 className="hm-capability-title">Four perspectives. One cohesive review.</h2><p className="hm-capability-body" style={{ marginTop: 16 }}>Specialist agents investigate different failure modes in parallel. Findings are consolidated before any review is delivered.</p></div>
          </div>
          <div className="hm-capability"><span className="hm-capability-kicker">02 / Repository context</span><div><h3 className="hm-capability-title">Look beyond the changed lines.</h3><p className="hm-capability-body" style={{ marginTop: 14 }}>Context retrieval helps agents reason about code in the surrounding project.</p></div></div>
          <div className="hm-capability"><span className="hm-capability-kicker">03 / Human judgment</span><div><h3 className="hm-capability-title">Keep people in control.</h3><p className="hm-capability-body" style={{ marginTop: 14 }}>Route findings that need a second look through the approval queue.</p></div></div>
          <div className="hm-capability"><span className="hm-capability-kicker">04 / Actionable output</span><div><h3 className="hm-capability-title">Findings that lead somewhere.</h3><p className="hm-capability-body" style={{ marginTop: 14 }}>File locations, severity and rationale make the next step clear.</p></div></div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 3: LIVE REVIEW DEMO (TRY WITHOUT SIGNUP)                    */}
      {/* ------------------------------------------------------------------ */}
      <section id="demo" className="px-3 sm:px-6 max-w-6xl mx-auto scroll-mt-24 min-w-0 max-w-full overflow-hidden">
        <div className="rounded-3xl border border-border bg-surface p-4 sm:p-8 space-y-6 shadow-xl min-w-0 max-w-full overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6 min-w-0">
            <div className="min-w-0">
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-accent/10 text-accent text-xs font-mono font-semibold mb-2 max-w-full break-words">
                Interactive playground · No sign-up required
              </div>
              <h2 className="text-xl sm:text-2xl font-bold font-mono text-foreground break-words">Test a real pull request review</h2>
              <p className="text-xs text-muted mt-1 break-words">
                Select a code sample or review the simulated output from our four parallel specialist agents.
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleRunReview}
                disabled={isRunningReview}
                className="inline-flex min-h-[44px] items-center px-4 py-2 rounded-xl bg-primary-action text-white dark:text-black text-xs font-semibold hover:opacity-90 active:scale-[0.98] transition-transform duration-150 ease-out disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                {isRunningReview ? "Analyzing diff..." : "Run review again"}
              </button>
            </div>
          </div>

          {/* Sample Preset Tabs */}
          <div className="flex flex-wrap gap-2 min-w-0">
            {SAMPLE_DIFFS.map((diff) => (
              <button
                key={diff.id}
                type="button"
                onClick={() => {
                  setSelectedDiffId(diff.id);
                  setHasRun(true);
                }}
                className={`min-h-[44px] px-3 sm:px-3.5 py-2 rounded-xl text-xs font-mono transition-all duration-150 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent border max-w-full truncate ${
                  selectedDiffId === diff.id
                    ? "bg-panel text-foreground font-semibold border-border shadow-xs"
                    : "text-muted hover:text-foreground border-transparent hover:bg-panel/40"
                }`}
              >
                {diff.name}
              </button>
            ))}
          </div>

          {/* Diff Viewer & Live Findings Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-w-0 max-w-full">
            {/* Input Diff */}
            <div className="rounded-2xl border border-border bg-bg p-3.5 sm:p-4 flex flex-col min-w-0 max-w-full overflow-hidden">
              <div className="flex items-center justify-between pb-3 border-b border-border/80 text-xs font-mono text-muted min-w-0">
                <span className="break-all mr-2">{currentDiff.repo} · Diff</span>
                <span className="text-[11px] shrink-0">{currentDiff.language}</span>
              </div>
              <pre className="mt-3 text-xs font-mono text-foreground overflow-x-auto leading-relaxed flex-1 min-w-0 max-w-full">
                <code>{currentDiff.diff}</code>
              </pre>
            </div>

            {/* Generated Review Findings */}
            <div className="rounded-2xl border border-border bg-panel/40 p-3.5 sm:p-4 flex flex-col space-y-4 min-w-0 max-w-full overflow-hidden">
              <div className="flex items-center justify-between pb-3 border-b border-border text-xs font-mono min-w-0">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-semibold text-foreground shrink-0">Verdict:</span>
                  <span className="px-2 py-0.5 rounded bg-err/20 text-err text-[11px] font-bold border border-err/30 break-words">
                    {currentDiff.verdict}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyMarkdown}
                  className="min-h-[36px] px-2.5 py-1 text-[11px] rounded-lg border border-border bg-surface text-muted hover:text-foreground transition-colors shrink-0"
                >
                  {copied ? "Copied markdown!" : "Copy markdown"}
                </button>
              </div>

              {isRunningReview ? (
                <div className="py-12 flex flex-col items-center justify-center gap-3 text-xs font-mono text-muted">
                  <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                  <span>Parallel agents checking syntax tree...</span>
                </div>
              ) : (
                <div className="space-y-3 flex-1 overflow-y-auto min-w-0">
                  {currentDiff.findings.map((f, i) => (
                    <div
                      key={i}
                      className="rounded-xl border border-border bg-surface p-3.5 space-y-2 text-xs min-w-0"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono font-bold text-foreground break-words min-w-0 flex-1">{f.title}</span>
                        <span className="px-1.5 py-0.5 rounded bg-panel font-mono text-[10px] text-muted uppercase shrink-0">
                          {f.agent}
                        </span>
                      </div>
                      <p className="text-muted leading-relaxed break-words">{f.description}</p>
                      <div className="text-[11px] font-mono text-muted/80 bg-bg px-2.5 py-1.5 rounded-lg border border-border/60 break-all min-w-0">
                        {f.file}:{f.line}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 4: HOW IT WORKS                                            */}
      {/* ------------------------------------------------------------------ */}
      <section id="how-it-works" className="px-3 sm:px-6 max-w-6xl mx-auto scroll-mt-24 space-y-10 sm:space-y-12 min-w-0 max-w-full">
        <div className="text-center max-w-2xl mx-auto space-y-3 min-w-0">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground break-words">How Hadron works</h2>
          <p className="text-xs sm:text-sm text-muted break-words">
            From webhook receipt to GitHub comment, every pull request passes through an isolated, multi-stage pipeline.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 sm:gap-6 min-w-0">
          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 space-y-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center font-mono font-bold text-xs text-accent">
              01
            </div>
            <h3 className="font-bold text-sm font-mono text-foreground break-words">Webhook ingestion</h3>
            <p className="text-xs text-muted leading-relaxed break-words">
              GitHub sends a pull request webhook. Hadron verifies the HMAC-SHA256 signature, enforces idempotency, and queues the review job.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 space-y-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center font-mono font-bold text-xs text-accent">
              02
            </div>
            <h3 className="font-bold text-sm font-mono text-foreground break-words">AST & context extraction</h3>
            <p className="text-xs text-muted leading-relaxed break-words">
              We extract git diff hunks and parse the Abstract Syntax Tree. Caller graphs and touched types are resolved before invoking models.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 space-y-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center font-mono font-bold text-xs text-accent">
              03
            </div>
            <h3 className="font-bold text-sm font-mono text-foreground break-words">Four parallel agents</h3>
            <p className="text-xs text-muted leading-relaxed break-words">
              Security, Code Quality, Test Coverage, and Documentation agents analyze the diff concurrently in isolated, sandboxed environments.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 space-y-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center font-mono font-bold text-xs text-accent">
              04
            </div>
            <h3 className="font-bold text-sm font-mono text-foreground break-words">Aggregated verdict</h3>
            <p className="text-xs text-muted leading-relaxed break-words">
              A judge node deduplicates findings, scores overall confidence, posts actionable inline comments to GitHub, or routes to human review.
            </p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 5: INTEGRATIONS                                            */}
      {/* ------------------------------------------------------------------ */}
      <section id="integrations" className="px-3 sm:px-6 max-w-6xl mx-auto scroll-mt-24 space-y-8 min-w-0 max-w-full">
        <div className="text-center max-w-2xl mx-auto space-y-3 min-w-0">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground break-words">Works with your developer stack</h2>
          <p className="text-xs sm:text-sm text-muted break-words">
            Connects directly to your GitHub pull requests with zero changes to existing CI workflows.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 min-w-0">
          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 space-y-3 min-w-0">
            <div className="font-mono text-xs font-semibold text-accent uppercase">Native App</div>
            <h3 className="font-bold text-base font-mono text-foreground break-words">GitHub App</h3>
            <p className="text-xs text-muted leading-relaxed break-words">
              One-click installation on individual repositories or entire organizations. Delivers inline review comments and status checks.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 space-y-3 min-w-0">
            <div className="font-mono text-xs font-semibold text-accent uppercase">CI Pipeline</div>
            <h3 className="font-bold text-base font-mono text-foreground break-words">GitHub Actions</h3>
            <p className="text-xs text-muted leading-relaxed break-words">
              Trigger reviews inside your existing CI workflow. Enforce blocking gates before deployment pipelines execute.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 space-y-3 min-w-0">
            <div className="font-mono text-xs font-semibold text-accent uppercase">REST & Webhooks</div>
            <h3 className="font-bold text-base font-mono text-foreground break-words">Custom Webhooks</h3>
            <p className="text-xs text-muted leading-relaxed break-words">
              RESTful APIs and webhook subscriptions allow engineering platforms to stream review telemetry into internal dashboards.
            </p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 5B: SPECIALIZED SOLUTIONS BY STACK                          */}
      {/* ------------------------------------------------------------------ */}
      <section id="solutions" className="px-3 sm:px-6 max-w-6xl mx-auto scroll-mt-24 space-y-8 min-w-0 max-w-full">
        <div className="text-center max-w-2xl mx-auto space-y-3 min-w-0">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-accent/10 text-accent text-xs font-mono font-semibold max-w-full break-words">
            Dedicated framework analyzers
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground break-words">Specialized solutions by stack</h2>
          <p className="text-xs sm:text-sm text-muted break-words">
            Static analysis rules crafted for your specific runtime, framework conventions, and concurrency models.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 min-w-0">
          <Link
            href="/solutions/python-security-audit"
            className="group rounded-2xl border border-border bg-surface p-6 flex flex-col justify-between space-y-4 hover:border-accent/40 transition-colors shadow-sm"
          >
            <div className="space-y-3">
              <div className="font-mono text-xs font-semibold text-accent uppercase">Python & Django</div>
              <h3 className="font-bold text-base font-mono text-foreground group-hover:text-accent transition-colors">
                Python Security Audit
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                Taint analysis across SQLAlchemy, raw SQL queries, and subprocess sinks to eliminate injections and CVEs.
              </p>
            </div>
            <span className="text-xs font-mono font-medium text-foreground flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
              Explore Python rules →
            </span>
          </Link>

          <Link
            href="/solutions/nextjs-pr-review"
            className="group rounded-2xl border border-border bg-surface p-6 flex flex-col justify-between space-y-4 hover:border-accent/40 transition-colors shadow-sm"
          >
            <div className="space-y-3">
              <div className="font-mono text-xs font-semibold text-accent uppercase">Next.js & React</div>
              <h3 className="font-bold text-base font-mono text-foreground group-hover:text-accent transition-colors">
                Next.js PR Review
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                Guarantees Server and Client Component separation, flags async fetch waterfalls, and checks Core Web Vitals.
              </p>
            </div>
            <span className="text-xs font-mono font-medium text-foreground flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
              Explore Next.js rules →
            </span>
          </Link>

          <Link
            href="/solutions/fastapi-code-quality"
            className="group rounded-2xl border border-border bg-surface p-6 flex flex-col justify-between space-y-4 hover:border-accent/40 transition-colors shadow-sm"
          >
            <div className="space-y-3">
              <div className="font-mono text-xs font-semibold text-accent uppercase">FastAPI & AsyncIO</div>
              <h3 className="font-bold text-base font-mono text-foreground group-hover:text-accent transition-colors">
                FastAPI Code Quality
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                Detects event loop blocking, validates async context managers, and audits Pydantic v2 migrations.
              </p>
            </div>
            <span className="text-xs font-mono font-medium text-foreground flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
              Explore FastAPI rules →
            </span>
          </Link>

          <Link
            href="/solutions/go-concurrency-checker"
            className="group rounded-2xl border border-border bg-surface p-6 flex flex-col justify-between space-y-4 hover:border-accent/40 transition-colors shadow-sm"
          >
            <div className="space-y-3">
              <div className="font-mono text-xs font-semibold text-accent uppercase">Golang Concurrency</div>
              <h3 className="font-bold text-base font-mono text-foreground group-hover:text-accent transition-colors">
                Go Concurrency Checker
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                Tracks goroutine termination paths, identifies unbuffered channel deadlocks, and enforces mutex lock ordering.
              </p>
            </div>
            <span className="text-xs font-mono font-medium text-foreground flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
              Explore Go rules →
            </span>
          </Link>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 6: SECURITY & PERMISSIONS (PLAIN WORDS)                    */}
      {/* ------------------------------------------------------------------ */}
      <section id="security" className="px-3 sm:px-6 max-w-6xl mx-auto scroll-mt-24 min-w-0 max-w-full">
        <div className="rounded-3xl border border-border bg-surface p-4 sm:p-8 md:p-10 space-y-8 min-w-0 max-w-full">
          <div className="max-w-2xl space-y-3 min-w-0">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-accent/10 text-accent text-xs font-mono font-semibold max-w-full break-words">
              Data protection & privacy
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground break-words">Security in plain English</h2>
            <p className="text-xs sm:text-sm text-muted break-words">
              Because an automated review engine reads pull requests, our security and privacy model is transparent and strictly bounded.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 min-w-0">
            <div className="space-y-2 min-w-0">
              <h3 className="font-bold text-sm font-mono text-foreground break-words">Read-only PR diff access</h3>
              <p className="text-xs text-muted leading-relaxed break-words">
                We only read the pull request diff and touched files necessary to complete the review. We never clone untouched repositories or access unpushed local code.
              </p>
            </div>

            <div className="space-y-2 min-w-0">
              <h3 className="font-bold text-sm font-mono text-foreground break-words">Zero model training</h3>
              <p className="text-xs text-muted leading-relaxed break-words">
                Your private code is never stored for training or used to train public or proprietary machine learning models. Code in transit is protected with TLS 1.3.
              </p>
            </div>

            <div className="space-y-2 min-w-0">
              <h3 className="font-bold text-sm font-mono text-foreground break-words">Isolated ephemeral execution</h3>
              <p className="text-xs text-muted leading-relaxed break-words">
                Every AST parse and syntax check executes in memory-isolated sandboxes with network egress completely blocked, terminating immediately after review.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 7: PRICING & ACCESS                                        */}
      {/* ------------------------------------------------------------------ */}
      <section id="pricing" className="px-3 sm:px-6 max-w-6xl mx-auto scroll-mt-24 space-y-8 min-w-0 max-w-full">
        <div className="text-center max-w-2xl mx-auto space-y-3 min-w-0">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground break-words">Developer-first pricing</h2>
          <p className="text-xs sm:text-sm text-muted break-words">Transparent access tiers for open source developers and engineering organizations.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 min-w-0">
          {/* Community */}
          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 flex flex-col justify-between space-y-6 min-w-0">
            <div className="space-y-4 min-w-0">
              <div>
                <h3 className="font-bold text-base font-mono text-foreground">Community</h3>
                <p className="text-xs text-muted mt-1">For individual developers and open source projects.</p>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground">Free</div>
              <ul className="text-xs text-muted space-y-2 font-mono">
                <li className="flex items-center gap-2">✓ Unlimited public repositories</li>
                <li className="flex items-center gap-2">✓ 4 parallel specialist agents</li>
                <li className="flex items-center gap-2">✓ GitHub pull request comments</li>
                <li className="flex items-center gap-2">✓ Community support</li>
              </ul>
            </div>
            <button
              type="button"
              onClick={openAccountModal}
              className="w-full inline-flex min-h-[44px] items-center justify-center rounded-xl border border-border bg-panel text-xs font-mono font-semibold text-foreground hover:bg-surface transition-colors"
            >
              Get started free
            </button>
          </div>

          {/* Team */}
          <div className="rounded-2xl border-2 border-accent bg-surface p-4 sm:p-6 flex flex-col justify-between space-y-6 relative shadow-xl min-w-0">
            <div className="absolute -top-3 right-4 sm:right-6 px-3 py-0.5 rounded-full bg-accent text-bg text-[10px] font-mono font-bold uppercase tracking-wider">
              Most Popular
            </div>
            <div className="space-y-4 min-w-0">
              <div>
                <h3 className="font-bold text-base font-mono text-foreground">Team</h3>
                <p className="text-xs text-muted mt-1">For growing teams shipping production software.</p>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground">
                $29 <span className="text-xs font-normal text-muted">/ dev / month</span>
              </div>
              <ul className="text-xs text-foreground space-y-2 font-mono">
                <li className="flex items-center gap-2">✓ Unlimited private repositories</li>
                <li className="flex items-center gap-2">✓ Custom review rule configuration</li>
                <li className="flex items-center gap-2">✓ Human-in-the-Loop review queue</li>
                <li className="flex items-center gap-2">✓ Priority queue execution</li>
                <li className="flex items-center gap-2">✓ Slack / Discord notifications</li>
              </ul>
            </div>
            <button
              type="button"
              onClick={openAccountModal}
              className="w-full inline-flex min-h-[44px] items-center justify-center rounded-xl bg-primary-action text-white dark:text-black text-xs font-mono font-semibold hover:opacity-90 transition-colors shadow-sm"
            >
              Start team trial
            </button>
          </div>

          {/* Enterprise */}
          <div className="rounded-2xl border border-border bg-surface p-4 sm:p-6 flex flex-col justify-between space-y-6 min-w-0">
            <div className="space-y-4 min-w-0">
              <div>
                <h3 className="font-bold text-base font-mono text-foreground">Enterprise</h3>
                <p className="text-xs text-muted mt-1">For security-sensitive or regulated engineering teams.</p>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground">Custom</div>
              <ul className="text-xs text-muted space-y-2 font-mono">
                <li className="flex items-center gap-2">✓ Self-hosted VPC deployment</li>
                <li className="flex items-center gap-2">✓ Bring your own LLM API keys</li>
                <li className="flex items-center gap-2">✓ SAML SSO / Okta integration</li>
                <li className="flex items-center gap-2">✓ Dedicated SLA & account manager</li>
              </ul>
            </div>
            <a
              href="mailto:team@hadron.vercel.app?subject=Hadron Enterprise Inquiry"
              className="w-full inline-flex min-h-[44px] items-center justify-center rounded-xl border border-border bg-panel text-xs font-mono font-semibold text-foreground hover:bg-surface transition-colors"
            >
              Contact engineering
            </a>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 8: SHORT FAQ (4-6 QUESTIONS)                               */}
      {/* ------------------------------------------------------------------ */}
      <section id="faq" className="px-3 sm:px-6 max-w-4xl mx-auto scroll-mt-24 space-y-8 min-w-0 max-w-full">
        <div className="text-center space-y-3 min-w-0">
          <h2 className="text-2xl sm:text-3xl font-extrabold font-mono text-foreground break-words">Frequently asked questions</h2>
          <p className="text-xs sm:text-sm text-muted break-words">Direct answers to technical and operational questions.</p>
        </div>

        <div className="space-y-4 min-w-0">
          {[
            {
              q: "How does Hadron prevent hallucinations common in AI chatbots?",
              a: "Rather than asking a single general-purpose chat model to review raw files, Hadron parses the Abstract Syntax Tree, extracts modified symbols, and runs deterministic rule validators. Every reported issue requires exact file, line number, and rule citations.",
            },
            {
              q: "Can Hadron automatically approve or block pull requests?",
              a: "Yes. Hadron can be added to your GitHub branch protection rules as a required status check. Depending on your configuration, clean reviews pass immediately, while critical security flaws request changes and block merge.",
            },
            {
              q: "What permissions does the GitHub App require?",
              a: "The GitHub App requests read access to pull request diffs and repository metadata, and write access to pull request reviews and status checks. It does not require admin, billing, or organization-level write permissions.",
            },
            {
              q: "How does the Human-in-the-Loop review queue work?",
              a: "When an agent computes confidence below your configured threshold (such as 85%), or flags high-risk database migrations, the PR is routed to your Hadron HITL queue for human sign-off before comments are published to GitHub.",
            },
            {
              q: "Does Hadron store or train on our code?",
              a: "No. Your source code is processed ephemerally in memory-isolated sandboxes with network egress blocked. Code is never used to train public or proprietary machine learning models.",
            },
          ].map((item, idx) => (
            <div key={idx} className="rounded-2xl border border-border bg-surface overflow-hidden min-w-0">
              <button
                type="button"
                onClick={() => setActiveFaq(activeFaq === idx ? null : idx)}
                className="w-full min-h-[44px] p-4 sm:p-5 text-left flex items-start sm:items-center justify-between gap-3 text-xs sm:text-sm font-mono font-semibold text-foreground hover:bg-panel/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent min-w-0"
                aria-expanded={activeFaq === idx}
              >
                <span className="break-words min-w-0 flex-1">{item.q}</span>
                <span className="text-muted shrink-0 text-base ml-2">{activeFaq === idx ? "−" : "+"}</span>
              </button>
              {activeFaq === idx && (
                <div className="px-4 sm:px-5 pb-4 sm:pb-5 pt-1 text-xs text-muted leading-relaxed font-sans border-t border-border/40 break-words min-w-0">
                  {item.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 9: CLOSING ACTION                                          */}
      {/* ------------------------------------------------------------------ */}
      <section className="px-3 sm:px-6 max-w-4xl mx-auto text-center min-w-0 max-w-full">
        <div className="rounded-3xl border border-border bg-surface p-5 sm:p-8 md:p-12 space-y-6 shadow-2xl relative overflow-hidden min-w-0 max-w-full">
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold font-mono text-foreground tracking-tight break-words">
            Stop letting security bugs slip into main.
          </h2>
          <p className="text-xs sm:text-sm text-muted max-w-xl mx-auto leading-relaxed break-words">
            Install the Hadron GitHub App in two minutes. Your next pull request will be autonomously evaluated across security, code quality, test coverage, and documentation.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={openAccountModal}
              className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center px-8 py-3 rounded-xl bg-primary-action text-white dark:text-black font-semibold text-sm hover:opacity-90 active:scale-[0.98] transition-transform duration-150 ease-out shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Install Hadron for GitHub
            </button>
            <Link
              href="/solutions/python-security-audit"
              className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center px-6 py-3 rounded-xl border border-border bg-surface text-foreground font-medium text-sm hover:bg-panel active:scale-[0.98] transition-transform duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Explore Solutions →
            </Link>
          </div>
          <p className="text-xs text-muted font-mono pt-2">
            No credit card required · Free for public repositories · 2-minute setup
          </p>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 10: HUMAN-FIRST DEVELOPER FOOTER & TOPICAL SITEMAP         */}
      {/* ------------------------------------------------------------------ */}
      <footer className="border-t border-border pt-12 pb-6 px-3 sm:px-6 max-w-6xl mx-auto text-xs font-mono text-muted space-y-8 min-w-0 max-w-full">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 sm:gap-8 min-w-0">
          <div className="space-y-3">
            <div className="font-bold text-foreground uppercase tracking-wider text-[11px]">Solutions</div>
            <ul className="space-y-2">
              <li>
                <Link href="/solutions/python-security-audit" className="hover:text-foreground transition-colors">
                  Python Security Audit
                </Link>
              </li>
              <li>
                <Link href="/solutions/nextjs-pr-review" className="hover:text-foreground transition-colors">
                  Next.js PR Review
                </Link>
              </li>
              <li>
                <Link href="/solutions/fastapi-code-quality" className="hover:text-foreground transition-colors">
                  FastAPI Code Quality
                </Link>
              </li>
              <li>
                <Link href="/solutions/go-concurrency-checker" className="hover:text-foreground transition-colors">
                  Go Concurrency Checker
                </Link>
              </li>
            </ul>
          </div>

          <div className="space-y-3">
            <div className="font-bold text-foreground uppercase tracking-wider text-[11px]">Platform</div>
            <ul className="space-y-2">
              <li>
                <Link href="/reviews" className="hover:text-foreground transition-colors">
                  Code Reviews
                </Link>
              </li>
              <li>
                <Link href="/hitl" className="hover:text-foreground transition-colors">
                  Human Triage Queue
                </Link>
              </li>
              <li>
                <Link href="/repositories" className="hover:text-foreground transition-colors">
                  Repositories
                </Link>
              </li>
              <li>
                <Link href="/economics" className="hover:text-foreground transition-colors">
                  Usage & Cost Ledger
                </Link>
              </li>
            </ul>
          </div>

          <div className="space-y-3">
            <div className="font-bold text-foreground uppercase tracking-wider text-[11px]">Observability</div>
            <ul className="space-y-2">
              <li>
                <Link href="/health" className="hover:text-foreground transition-colors">
                  System Health & Uptime
                </Link>
              </li>
              <li>
                <a href="/llms.txt" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
                  llms.txt (AI Discovery)
                </a>
              </li>
              <li>
                <a href="/sitemap.xml" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
                  Sitemap Index
                </a>
              </li>
              <li>
                <a href="/robots.txt" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
                  Robots Access Policy
                </a>
              </li>
            </ul>
          </div>

          <div className="space-y-3">
            <div className="font-bold text-foreground uppercase tracking-wider text-[11px]">Engineering</div>
            <ul className="space-y-2">
              <li>
                <a href="https://github.com/krishujeniya/Hadron" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
                  GitHub Repository
                </a>
              </li>
              <li>
                <span className="text-muted/60">Tree-sitter AST</span>
              </li>
              <li>
                <span className="text-muted/60">Tiger Cloud DiskANN</span>
              </li>
              <li>
                <span className="text-muted/60">LangGraph State Machine</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-border/60 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px]">
          <p>© 2026 Hadron. Autonomous pull request review engine for GitHub.</p>
          <p>Zero customer code training · Read-only PR diff access · Ephemeral sandboxes</p>
        </div>
      </footer>
    </div>
  );
}
