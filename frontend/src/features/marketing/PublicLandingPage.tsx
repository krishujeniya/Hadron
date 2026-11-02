"use client";

import { useState } from "react";
import Link from "next/link";
import { HadronLogo } from "@/components/brand/HadronLogo";
import { HadronIcon } from "@/components/brand/HadronIcon";
import { useGitHubAccount } from "@/features/auth/github-context";

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
    <div className="space-y-24 md:space-y-32 pb-20">
      {/* ------------------------------------------------------------------ */}
      {/* SECTION 1: HERO                                                    */}
      {/* ------------------------------------------------------------------ */}
      <section className="pt-8 md:pt-14 px-4 sm:px-6 max-w-6xl mx-auto">
        <div className="text-center max-w-3xl mx-auto space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-surface text-xs font-mono text-muted">
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse" aria-hidden="true" />
            <span>Autonomous code review for GitHub pull requests</span>
          </div>

          <h1 className="text-3xl sm:text-5xl md:text-6xl font-extrabold tracking-tight bg-gradient-to-b from-white via-zinc-100 to-zinc-400 dark:from-white dark:via-zinc-100 dark:to-zinc-400 bg-clip-text text-transparent leading-[1.12]">
            Autonomous code reviews that catch critical vulnerabilities, logic flaws, and test gaps before you merge.
          </h1>

          <p className="text-base sm:text-lg text-muted leading-relaxed max-w-2xl mx-auto font-sans">
            Four specialized review agents inspect your pull request diffs in parallel, analyzing syntax trees and test suites to post deterministic, actionable reviews directly to GitHub.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={openAccountModal}
              className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center px-6 py-3 rounded-xl bg-primary-action text-white dark:text-black font-semibold text-sm hover:opacity-90 active:scale-95 transition-all shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
              Install GitHub App
            </button>

            <a
              href="#demo"
              className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center px-6 py-3 rounded-xl border border-border bg-surface text-foreground font-medium text-sm hover:bg-panel active:scale-95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Try live review (No sign-up) →
            </a>
          </div>

          <p className="text-xs text-muted font-mono">
            Free for public repositories · Read-only PR diff access · Zero code training
          </p>
        </div>

        {/* Real Review Sample Card on PR #142 */}
        <div className="mt-12 max-w-4xl mx-auto rounded-2xl border border-border bg-surface overflow-hidden shadow-2xl">
          {/* GitHub PR Simulated Header */}
          <div className="bg-panel/70 border-b border-border px-4 py-3 flex flex-wrap items-center justify-between gap-3 font-mono text-xs">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-ok" aria-hidden="true" />
              <span className="text-muted">octocat / auth-service</span>
              <span className="text-muted">·</span>
              <span className="font-semibold text-foreground">PR #142</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-muted">12 files changed (+340 -82)</span>
              <span className="px-2 py-0.5 rounded bg-err/20 text-err text-[11px] font-semibold border border-err/30">
                CHANGES RECOMMENDED
              </span>
            </div>
          </div>

          {/* GitHub Review Body */}
          <div className="p-5 sm:p-6 space-y-5">
            <div className="flex items-start gap-3">
              <HadronIcon size={32} animated={false} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-sm text-foreground font-mono">Hadron Bot</span>
                    <span className="text-xs text-muted ml-2">commented on PR #142</span>
                  </div>
                  <span className="text-[11px] font-mono text-muted">automated review</span>
                </div>
                <p className="text-xs text-muted mt-1">
                  Evaluated security, code quality, test coverage, and documentation contracts across modified files.
                </p>
              </div>
            </div>

            {/* Finding Item: Security */}
            <div className="rounded-xl border border-err/30 bg-err/5 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-err/20 text-err text-[10px] font-mono font-bold uppercase tracking-wider">
                    Security Agent
                  </span>
                  <span className="font-semibold text-xs text-foreground font-mono">backend/auth/token.py:84</span>
                </div>
                <span className="text-[11px] font-mono text-muted">94% confidence</span>
              </div>
              <p className="text-xs text-foreground font-medium">
                Potential race condition in session invalidation check under multi-replica deployments.
              </p>
              <div className="rounded-lg bg-bg p-3 font-mono text-xs overflow-x-auto border border-border/80">
                <div className="text-err/90">- if token in in_memory_revocations: return False</div>
                <div className="text-ok/90">+ if await redis.sismember(&quot;revoked_tokens&quot;, token): return False</div>
              </div>
              <p className="text-[11px] text-muted">
                Rule: SEC-AUTH-004 · In-memory cache is not synchronized between stateless API instances. Use distributed Redis set.
              </p>
            </div>

            {/* Finding Item: Test Coverage */}
            <div className="rounded-xl border border-warn/30 bg-warn/5 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-warn/20 text-warn text-[10px] font-mono font-bold uppercase tracking-wider">
                    Test Agent
                  </span>
                  <span className="font-semibold text-xs text-foreground font-mono">tests/test_auth.py:112</span>
                </div>
                <span className="text-[11px] font-mono text-muted">91% confidence</span>
              </div>
              <p className="text-xs text-foreground font-medium">
                Missing unit test for empty or malformed token string edge cases.
              </p>
              <p className="text-[11px] text-muted font-mono">
                Suggestion: Add test_revocation_empty_token_returns_401 to ensure early exit before Redis query.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 2: PROOF METRICS                                           */}
      {/* ------------------------------------------------------------------ */}
      <section className="px-4 sm:px-6 max-w-6xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-border bg-surface p-5 text-center">
            <div className="text-3xl sm:text-4xl font-extrabold font-mono text-foreground">4</div>
            <div className="text-xs font-mono font-semibold text-accent uppercase tracking-wider mt-1">Specialist agents</div>
            <p className="text-[11px] text-muted mt-2">Security, Quality, Test, and Docs evaluate in parallel.</p>
          </div>
          <div className="rounded-2xl border border-border bg-surface p-5 text-center">
            <div className="text-3xl sm:text-4xl font-extrabold font-mono text-foreground">&lt;18s</div>
            <div className="text-xs font-mono font-semibold text-accent uppercase tracking-wider mt-1">Review latency</div>
            <p className="text-[11px] text-muted mt-2">Average time from webhook receipt to GitHub comment.</p>
          </div>
          <div className="rounded-2xl border border-border bg-surface p-5 text-center">
            <div className="text-3xl sm:text-4xl font-extrabold font-mono text-foreground">100%</div>
            <div className="text-xs font-mono font-semibold text-accent uppercase tracking-wider mt-1">Verifiable citations</div>
            <p className="text-[11px] text-muted mt-2">Every issue pinned to exact file and line ranges.</p>
          </div>
          <div className="rounded-2xl border border-border bg-surface p-5 text-center">
            <div className="text-3xl sm:text-4xl font-extrabold font-mono text-foreground">0</div>
            <div className="text-xs font-mono font-semibold text-accent uppercase tracking-wider mt-1">Hallucinated rules</div>
            <p className="text-[11px] text-muted mt-2">Grounded in concrete syntax tree checks, not loose chat.</p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 3: LIVE REVIEW DEMO (TRY WITHOUT SIGNUP)                    */}
      {/* ------------------------------------------------------------------ */}
      <section id="demo" className="px-4 sm:px-6 max-w-6xl mx-auto scroll-mt-24">
        <div className="rounded-3xl border border-border bg-surface p-6 sm:p-8 space-y-6 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
            <div>
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-accent/10 text-accent text-xs font-mono font-semibold mb-2">
                Interactive playground · No sign-up required
              </div>
              <h2 className="text-2xl font-bold font-mono text-foreground">Test a real pull request review</h2>
              <p className="text-xs text-muted mt-1">
                Select a code sample or review the simulated output from our four parallel specialist agents.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleRunReview}
                disabled={isRunningReview}
                className="inline-flex min-h-[44px] items-center px-4 py-2 rounded-xl bg-primary-action text-white dark:text-black text-xs font-semibold hover:opacity-90 active:scale-95 transition-all disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                {isRunningReview ? "Analyzing diff..." : "Run review again"}
              </button>
            </div>
          </div>

          {/* Sample Preset Tabs */}
          <div className="flex flex-wrap gap-2">
            {SAMPLE_DIFFS.map((diff) => (
              <button
                key={diff.id}
                type="button"
                onClick={() => {
                  setSelectedDiffId(diff.id);
                  setHasRun(true);
                }}
                className={`min-h-[44px] px-3.5 py-2 rounded-xl text-xs font-mono transition-all border ${
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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Input Diff */}
            <div className="rounded-2xl border border-border bg-bg p-4 flex flex-col">
              <div className="flex items-center justify-between pb-3 border-b border-border/80 text-xs font-mono text-muted">
                <span>{currentDiff.repo} · Pull request diff</span>
                <span className="text-[11px]">{currentDiff.language}</span>
              </div>
              <pre className="mt-3 text-xs font-mono text-foreground overflow-x-auto leading-relaxed flex-1">
                <code>{currentDiff.diff}</code>
              </pre>
            </div>

            {/* Generated Review Findings */}
            <div className="rounded-2xl border border-border bg-panel/40 p-4 flex flex-col space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-border text-xs font-mono">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-foreground">Hadron Verdict:</span>
                  <span className="px-2 py-0.5 rounded bg-err/20 text-err text-[11px] font-bold border border-err/30">
                    {currentDiff.verdict}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyMarkdown}
                  className="min-h-[36px] px-2.5 py-1 text-[11px] rounded-lg border border-border bg-surface text-muted hover:text-foreground transition-colors"
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
                <div className="space-y-3 flex-1 overflow-y-auto">
                  {currentDiff.findings.map((f, i) => (
                    <div
                      key={i}
                      className="rounded-xl border border-border bg-surface p-3.5 space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-foreground">{f.title}</span>
                        <span className="px-1.5 py-0.5 rounded bg-panel font-mono text-[10px] text-muted uppercase">
                          {f.agent}
                        </span>
                      </div>
                      <p className="text-muted leading-relaxed">{f.description}</p>
                      <div className="text-[11px] font-mono text-muted/80 bg-bg px-2.5 py-1.5 rounded-lg border border-border/60">
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
      <section id="how-it-works" className="px-4 sm:px-6 max-w-6xl mx-auto scroll-mt-24 space-y-12">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <h2 className="text-3xl font-extrabold font-mono text-foreground">How Hadron works</h2>
          <p className="text-sm text-muted">
            From webhook receipt to GitHub comment, every pull request passes through an isolated, multi-stage pipeline.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
            <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center font-mono font-bold text-xs text-accent">
              01
            </div>
            <h3 className="font-bold text-sm font-mono text-foreground">Webhook ingestion</h3>
            <p className="text-xs text-muted leading-relaxed">
              GitHub sends a pull request webhook. Hadron verifies the HMAC-SHA256 signature, enforces idempotency, and queues the review job.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
            <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center font-mono font-bold text-xs text-accent">
              02
            </div>
            <h3 className="font-bold text-sm font-mono text-foreground">AST & context extraction</h3>
            <p className="text-xs text-muted leading-relaxed">
              We extract git diff hunks and parse the Abstract Syntax Tree. Caller graphs and touched types are resolved before invoking models.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
            <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center font-mono font-bold text-xs text-accent">
              03
            </div>
            <h3 className="font-bold text-sm font-mono text-foreground">Four parallel agents</h3>
            <p className="text-xs text-muted leading-relaxed">
              Security, Code Quality, Test Coverage, and Documentation agents analyze the diff concurrently in isolated, sandboxed environments.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
            <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center font-mono font-bold text-xs text-accent">
              04
            </div>
            <h3 className="font-bold text-sm font-mono text-foreground">Aggregated verdict</h3>
            <p className="text-xs text-muted leading-relaxed">
              A judge node deduplicates findings, scores overall confidence, posts actionable inline comments to GitHub, or routes to human review.
            </p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 5: INTEGRATIONS                                            */}
      {/* ------------------------------------------------------------------ */}
      <section id="integrations" className="px-4 sm:px-6 max-w-6xl mx-auto scroll-mt-24 space-y-8">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <h2 className="text-3xl font-extrabold font-mono text-foreground">Works with your developer stack</h2>
          <p className="text-sm text-muted">
            Connects directly to your GitHub pull requests with zero changes to existing CI workflows.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
            <div className="font-mono text-xs font-semibold text-accent uppercase">Native App</div>
            <h3 className="font-bold text-base font-mono text-foreground">GitHub App</h3>
            <p className="text-xs text-muted leading-relaxed">
              One-click installation on individual repositories or entire organizations. Delivers inline review comments and status checks.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
            <div className="font-mono text-xs font-semibold text-accent uppercase">CI Pipeline</div>
            <h3 className="font-bold text-base font-mono text-foreground">GitHub Actions</h3>
            <p className="text-xs text-muted leading-relaxed">
              Trigger reviews inside your existing CI workflow. Enforce blocking gates before deployment pipelines execute.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface p-6 space-y-3">
            <div className="font-mono text-xs font-semibold text-accent uppercase">REST & Webhooks</div>
            <h3 className="font-bold text-base font-mono text-foreground">Custom Webhooks</h3>
            <p className="text-xs text-muted leading-relaxed">
              RESTful APIs and webhook subscriptions allow engineering platforms to stream review telemetry into internal dashboards.
            </p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 6: SECURITY & PERMISSIONS (PLAIN WORDS)                    */}
      {/* ------------------------------------------------------------------ */}
      <section id="security" className="px-4 sm:px-6 max-w-6xl mx-auto scroll-mt-24">
        <div className="rounded-3xl border border-border bg-surface p-8 sm:p-10 space-y-8">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-accent/10 text-accent text-xs font-mono font-semibold">
              Data protection & privacy
            </div>
            <h2 className="text-3xl font-extrabold font-mono text-foreground">Security in plain English</h2>
            <p className="text-sm text-muted">
              Because an automated review engine reads pull requests, our security and privacy model is transparent and strictly bounded.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <h3 className="font-bold text-sm font-mono text-foreground">Read-only PR diff access</h3>
              <p className="text-xs text-muted leading-relaxed">
                We only read the pull request diff and touched files necessary to complete the review. We never clone untouched repositories or access unpushed local code.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="font-bold text-sm font-mono text-foreground">Zero model training</h3>
              <p className="text-xs text-muted leading-relaxed">
                Your private code is never stored for training or used to train public or proprietary machine learning models. Code in transit is protected with TLS 1.3.
              </p>
            </div>

            <div className="space-y-2">
              <h3 className="font-bold text-sm font-mono text-foreground">Isolated ephemeral execution</h3>
              <p className="text-xs text-muted leading-relaxed">
                Every AST parse and syntax check executes in memory-isolated sandboxes with network egress completely blocked, terminating immediately after review.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* SECTION 7: PRICING & ACCESS                                        */}
      {/* ------------------------------------------------------------------ */}
      <section id="pricing" className="px-4 sm:px-6 max-w-6xl mx-auto scroll-mt-24 space-y-8">
        <div className="text-center max-w-2xl mx-auto space-y-3">
          <h2 className="text-3xl font-extrabold font-mono text-foreground">Developer-first pricing</h2>
          <p className="text-sm text-muted">Transparent access tiers for open source developers and engineering organizations.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Community */}
          <div className="rounded-2xl border border-border bg-surface p-6 flex flex-col justify-between space-y-6">
            <div className="space-y-4">
              <div>
                <h3 className="font-bold text-base font-mono text-foreground">Community</h3>
                <p className="text-xs text-muted mt-1">For individual developers and open source projects.</p>
              </div>
              <div className="text-3xl font-extrabold font-mono text-foreground">Free</div>
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
          <div className="rounded-2xl border-2 border-accent bg-surface p-6 flex flex-col justify-between space-y-6 relative shadow-xl">
            <div className="absolute -top-3 right-6 px-3 py-0.5 rounded-full bg-accent text-bg text-[10px] font-mono font-bold uppercase tracking-wider">
              Most Popular
            </div>
            <div className="space-y-4">
              <div>
                <h3 className="font-bold text-base font-mono text-foreground">Team</h3>
                <p className="text-xs text-muted mt-1">For growing teams shipping production software.</p>
              </div>
              <div className="text-3xl font-extrabold font-mono text-foreground">
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
          <div className="rounded-2xl border border-border bg-surface p-6 flex flex-col justify-between space-y-6">
            <div className="space-y-4">
              <div>
                <h3 className="font-bold text-base font-mono text-foreground">Enterprise</h3>
                <p className="text-xs text-muted mt-1">For security-sensitive or regulated engineering teams.</p>
              </div>
              <div className="text-3xl font-extrabold font-mono text-foreground">Custom</div>
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
      <section id="faq" className="px-4 sm:px-6 max-w-4xl mx-auto scroll-mt-24 space-y-8">
        <div className="text-center space-y-3">
          <h2 className="text-3xl font-extrabold font-mono text-foreground">Frequently asked questions</h2>
          <p className="text-sm text-muted">Direct answers to technical and operational questions.</p>
        </div>

        <div className="space-y-4">
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
            <div key={idx} className="rounded-2xl border border-border bg-surface overflow-hidden">
              <button
                type="button"
                onClick={() => setActiveFaq(activeFaq === idx ? null : idx)}
                className="w-full min-h-[44px] p-5 text-left flex items-center justify-between gap-4 text-sm font-mono font-semibold text-foreground hover:bg-panel/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                aria-expanded={activeFaq === idx}
              >
                <span>{item.q}</span>
                <span className="text-muted shrink-0 text-base">{activeFaq === idx ? "−" : "+"}</span>
              </button>
              {activeFaq === idx && (
                <div className="px-5 pb-5 pt-1 text-xs text-muted leading-relaxed font-sans border-t border-border/40">
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
      <section className="px-4 sm:px-6 max-w-4xl mx-auto text-center">
        <div className="rounded-3xl border border-border bg-surface p-8 sm:p-12 space-y-6 shadow-2xl relative overflow-hidden">
          <h2 className="text-3xl sm:text-4xl font-extrabold font-mono text-foreground tracking-tight">
            Stop letting security bugs slip into main.
          </h2>
          <p className="text-sm text-muted max-w-xl mx-auto leading-relaxed">
            Install the Hadron GitHub App in two minutes. Your next pull request will be autonomously evaluated across security, code quality, test coverage, and documentation.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={openAccountModal}
              className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center px-8 py-3 rounded-xl bg-primary-action text-white dark:text-black font-semibold text-sm hover:opacity-90 active:scale-95 transition-all shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Install Hadron for GitHub
            </button>
            <Link
              href="/solutions/python-security-audit"
              className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center px-6 py-3 rounded-xl border border-border bg-surface text-foreground font-medium text-sm hover:bg-panel active:scale-95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Explore Solutions →
            </Link>
          </div>
          <p className="text-xs text-muted font-mono pt-2">
            No credit card required · Free for public repositories · 2-minute setup
          </p>
        </div>
      </section>
    </div>
  );
}
