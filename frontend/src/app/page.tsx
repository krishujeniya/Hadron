"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useGitHubAccount } from "@/lib/githubContext";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import { Status } from "@/components/ui/Status";
import { Button } from "@/components/ui/Button";
import { NonTechReviewCard } from "@/components/NonTechReviewCard";
import { PlainEnglishAssistant } from "@/components/PlainEnglishAssistant";
import type { HITLItem, Paginated, ReviewSummary } from "@/lib/types";

export default function DashboardPage() {
  const { currentAccount, repositories, openAccountModal } = useGitHubAccount();
  const [viewMode, setViewMode] = useState<"executive" | "developer">("executive");

  // Synchronize view preference across storage events and command palette (T34)
  useEffect(() => {
    const syncMode = () => {
      try {
        const saved = localStorage.getItem("hadron_view_mode");
        if (saved === "developer" || saved === "executive") {
          setViewMode(saved);
        }
      } catch {}
    };
    syncMode();
    window.addEventListener("storage", syncMode);
    return () => window.removeEventListener("storage", syncMode);
  }, []);

  const setMode = (mode: "executive" | "developer") => {
    setViewMode(mode);
    try {
      localStorage.setItem("hadron_view_mode", mode);
      window.dispatchEvent(new Event("storage"));
    } catch {}
  };

  const accountParam = currentAccount ? `&account=${encodeURIComponent(currentAccount.login)}` : "";
  const { data: reviewsResp, error: reviewsErr } =
    useSWR<Paginated<ReviewSummary>>(`/api/v1/reviews?limit=50${accountParam}`);
  const { data: hitlResp, error: hitlErr } =
    useSWR<Paginated<HITLItem>>(`/api/v1/hitl/queue?limit=50${accountParam}`);

  const allReviews = reviewsResp?.items ?? [];
  const allHitl = hitlResp?.items ?? [];

  // Filter client-side as well to guarantee strict account scoping
  const reviews = currentAccount
    ? allReviews.filter((r) => r.repo_full_name.toLowerCase().startsWith(`${currentAccount.login.toLowerCase()}/`))
    : allReviews;
  const hitl = currentAccount
    ? allHitl.filter((h) => h.repo_full_name.toLowerCase().startsWith(`${currentAccount.login.toLowerCase()}/`))
    : allHitl;

  // Segment reviews into actionable operational buckets (T34)
  const pendingHitl = hitl.filter((h) => h.status === "pending" || h.status === "in_review");
  const runningReviews = reviews.filter((r) =>
    ["queued", "received", "in_progress", "agents_running", "aggregating", "posting"].includes(r.status)
  );
  const failedReviews = reviews.filter((r) => r.status === "failed");
  const completedReviews = reviews.filter((r) => r.status === "completed" || r.status === "escalated");
  const recentReviews = reviews.slice(0, 8);

  // Determine state-aware primary action (T34)
  let actionTitle = "Operational Overview";
  let actionDescription = "All monitored repositories are active.";
  let actionLink = "/reviews";
  let actionLabel = "Browse Reviews";
  let actionTone: "warning" | "error" | "info" | "neutral" = "neutral";

  if (pendingHitl.length > 0) {
    actionTitle = `${pendingHitl.length} Human Decision${pendingHitl.length === 1 ? "" : "s"} Pending`;
    actionDescription = "Specialist agents escalated pull requests requiring human sign-off before merge.";
    actionLink = "/hitl";
    actionLabel = "Review Approvals Queue →";
    actionTone = "warning";
  } else if (failedReviews.length > 0) {
    actionTitle = `${failedReviews.length} Review${failedReviews.length === 1 ? "" : "s"} Failed`;
    actionDescription = "Reviews encountered unexpected execution errors or timeouts.";
    actionLink = "/reviews?status=failed";
    actionLabel = "Inspect Failed Reviews →";
    actionTone = "error";
  } else if (runningReviews.length > 0) {
    actionTitle = `${runningReviews.length} Review${runningReviews.length === 1 ? "" : "s"} Actively Processing`;
    actionDescription = "Specialist security, quality, test, and documentation agents are running over diffs.";
    actionLink = "/reviews";
    actionLabel = "Monitor Reviews →";
    actionTone = "info";
  } else if (repositories.length === 0) {
    actionTitle = "No Repositories Connected";
    actionDescription = "Connect your GitHub organization or repository to begin automated code reviews.";
    actionLink = "/repositories";
    actionLabel = "Connect Repository →";
    actionTone = "info";
  }

  return (
    <div className="space-y-8">
      {/* Account Context Banner */}
      {currentAccount ? (
        <div className="border border-border rounded-2xl bg-surface p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-sm">
          <div className="flex items-center gap-3">
            {currentAccount.avatar_url ? (
              <img
                src={currentAccount.avatar_url}
                alt={currentAccount.login}
                width={40}
                height={40}
                className="w-10 h-10 rounded-full border border-border shrink-0"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold shrink-0">
                {currentAccount.login.slice(0, 2).toUpperCase()}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-foreground">Workspace:</span>
                <span className="font-mono text-foreground font-medium">@{currentAccount.login}</span>
                <Status variant="info" label="Scoped" showDot={false} />
              </div>
              <p className="text-muted text-xs mt-0.5">
                Monitoring {repositories.length} repositories. Data is isolated to @{currentAccount.login}.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/repositories">
              <Button variant="secondary" size="sm">
                Repositories ({repositories.length})
              </Button>
            </Link>
            <Button onClick={openAccountModal} variant="primary" size="sm">
              Switch Workspace
            </Button>
          </div>
        </div>
      ) : null}

      {/* State-Aware Action Banner (T34) */}
      <div
        className={`p-4 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm transition-all ${
          actionTone === "warning"
            ? "border-warn/40 bg-warn/10 text-foreground"
            : actionTone === "error"
            ? "border-err/40 bg-err/10 text-foreground"
            : actionTone === "info"
            ? "border-accent/40 bg-accent/10 text-foreground"
            : "border-border bg-surface text-foreground"
        }`}
      >
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-base font-mono">{actionTitle}</span>
            {actionTone === "warning" && <Status variant="warning" label="Action Required" />}
            {actionTone === "error" && <Status variant="error" label="Attention Needed" />}
          </div>
          <p className="text-xs text-muted mt-1 max-w-xl">{actionDescription}</p>
        </div>
        <Link href={actionLink}>
          <Button variant={actionTone === "warning" ? "danger" : "primary"} size="sm">
            {actionLabel}
          </Button>
        </Link>
      </div>

      {/* Top Header & Interactive Mode Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
            {viewMode === "executive" ? "Executive summary and guidance" : "Developer operations overview"}
          </h1>
          <p className="text-muted text-sm mt-1">
            {viewMode === "executive"
              ? "Actionable code review findings translated into plain English for decision-makers."
              : "Autonomous multi-agent review pipeline status, running jobs, and escalation queues."}
          </p>
        </div>

        {/* View Mode Switcher */}
        <div className="inline-flex p-1 rounded-xl bg-panel border border-border">
          <button
            type="button"
            onClick={() => setMode("executive")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              viewMode === "executive"
                ? "bg-surface text-foreground shadow-sm border border-border"
                : "text-muted hover:text-foreground"
            }`}
          >
            <span>Plain English</span>
          </button>
          <button
            type="button"
            onClick={() => setMode("developer")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              viewMode === "developer"
                ? "bg-surface text-foreground shadow-sm border border-border"
                : "text-muted hover:text-foreground"
            }`}
          >
            <span>Developer View</span>
          </button>
        </div>
      </div>

      {/* Actionable Review Sections */}
      {viewMode === "executive" ? (
        <div className="space-y-8">
          <PlainEnglishAssistant
            recentReviews={reviews}
            accountName={currentAccount?.login}
          />

          {/* Non-Tech Review Impact Cards */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-foreground flex items-center gap-2 font-mono">
                  Recent pull request impacts
                </h2>
                <p className="text-xs text-muted">
                  Every pull request translated into business impact and review status.
                </p>
              </div>
              <Link href="/reviews" className="text-xs font-medium text-accent hover:underline font-mono">
                View all reviews →
              </Link>
            </div>

            {reviewsErr ? (
              <Empty>Could not load reviews: {String(reviewsErr.message)}</Empty>
            ) : recentReviews.length === 0 ? (
              <Empty>
                {currentAccount
                  ? `No reviews recorded yet for @${currentAccount.login}. When developers open a PR, Hadron will show review findings here.`
                  : "No reviews yet. Connect a repository and open a pull request."}
              </Empty>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {recentReviews.map((r) => (
                  <NonTechReviewCard key={r.id} review={r} />
                ))}
              </div>
            )}
          </section>
        </div>
      ) : (
        /* DEVELOPER TECHNICAL VIEW */
        <div className="space-y-8">
          {/* Operational Metrics Cards */}
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total Reviews" value={reviewsResp?.total ?? reviews.length} err={!!reviewsErr} />
            <StatCard label="Watched Repos" value={repositories.length} tone="ok" />
            <StatCard
              label="Approvals Pending"
              value={hitlResp?.total ?? pendingHitl.length}
              err={!!hitlErr}
              tone={pendingHitl.length > 0 ? "warn" : "ok"}
            />
            <StatCard
              label="Running Reviews"
              value={runningReviews.length}
              err={!!reviewsErr}
              tone={runningReviews.length > 0 ? "info" : "neutral"}
            />
          </section>

          {/* 1. Pending Human Decisions */}
          {pendingHitl.length > 0 && (
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-semibold text-foreground font-mono">
                    Pending Human Decisions ({pendingHitl.length})
                  </h2>
                  <Status variant="warning" label="Action Needed" />
                </div>
                <Link href="/hitl" className="text-xs text-accent hover:underline font-mono">
                  Open Approvals Queue →
                </Link>
              </div>
              <div className="border border-border rounded-xl bg-surface divide-y divide-border overflow-hidden shadow-sm">
                {pendingHitl.slice(0, 5).map((h) => (
                  <Link
                    key={h.id}
                    href={`/hitl/${encodeURIComponent(h.id)}`}
                    className="flex items-center justify-between px-4 py-3 hover:bg-panel transition-colors gap-3"
                  >
                    <div className="min-w-0">
                      <div className="font-mono text-sm font-semibold text-foreground">
                        {h.repo_full_name} #{h.pr_number}
                      </div>
                      <div className="text-xs text-muted truncate mt-0.5">
                        {h.escalation_reason}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <VerdictChip verdict={h.agent_verdict} />
                      <span className="text-xs font-medium text-accent">Decide →</span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* 2. In-Flight Reviews */}
          {runningReviews.length > 0 && (
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-semibold text-foreground font-mono">
                    Running Reviews ({runningReviews.length})
                  </h2>
                  <Status variant="info" label="In-Flight" />
                </div>
                <Link href="/reviews" className="text-xs text-accent hover:underline font-mono">
                  View All →
                </Link>
              </div>
              <div className="border border-border rounded-xl bg-surface divide-y divide-border overflow-hidden shadow-sm">
                {runningReviews.map((r) => (
                  <Link
                    key={r.id}
                    href={`/reviews/${encodeURIComponent(r.id)}`}
                    className="flex items-center justify-between px-4 py-3 hover:bg-panel transition-colors gap-3"
                  >
                    <div className="min-w-0">
                      <div className="font-mono text-sm font-semibold text-foreground">
                        {r.repo_full_name} #{r.pr_number}
                      </div>
                      <div className="text-xs text-muted truncate mt-0.5">
                        {r.pr_title || "Review in progress..."}
                      </div>
                    </div>
                    <ReviewStatusBadge status={r.status} />
                  </Link>
                ))}
              </div>
            </section>
          )}

          {/* 3. Recent Reviews */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-foreground font-mono">Recent Reviews</h2>
                {currentAccount && (
                  <span className="text-xs text-muted font-mono">
                    (@{currentAccount.login})
                  </span>
                )}
              </div>
              <Link href="/reviews" className="text-xs text-accent hover:underline font-mono">
                View all reviews ({reviewsResp?.total ?? reviews.length}) →
              </Link>
            </div>
            {reviewsErr ? (
              <Empty>Could not load reviews: {String(reviewsErr.message)}</Empty>
            ) : recentReviews.length === 0 ? (
              <Empty>
                {currentAccount
                  ? `No reviews recorded yet for @${currentAccount.login}. Pull requests sent to watched repositories will show up here.`
                  : "No reviews yet. Open a PR on a watched repository."}
              </Empty>
            ) : (
              <div className="border border-border rounded-xl bg-surface divide-y divide-border overflow-hidden shadow-sm">
                {recentReviews.map((r) => (
                  <Link
                    key={r.id}
                    href={`/reviews/${encodeURIComponent(r.id)}`}
                    className="flex items-center justify-between px-4 py-3 hover:bg-panel transition-colors gap-3"
                  >
                    <div className="min-w-0">
                      <div className="font-mono text-sm font-semibold text-foreground">
                        {r.repo_full_name} #{r.pr_number}
                      </div>
                      <div className="text-xs text-muted truncate mt-0.5">
                        {r.pr_title || `Pull request #${r.pr_number}`}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <VerdictChip verdict={r.verdict} />
                      <ReviewStatusBadge status={r.status} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  err,
  tone,
}: {
  label: string;
  value?: number;
  err?: boolean;
  tone?: "ok" | "warn" | "err" | "info" | "neutral";
}) {
  const toneColor =
    tone === "ok"
      ? "text-ok"
      : tone === "warn"
      ? "text-warn"
      : tone === "err"
      ? "text-err"
      : tone === "info"
      ? "text-accent"
      : "text-foreground";

  return (
    <div className="border border-border rounded-xl bg-surface px-4 py-3.5 hover:border-muted/50 transition-all shadow-sm">
      <div className="text-xs uppercase tracking-wider font-mono text-muted">{label}</div>
      <div className={`text-2xl font-mono font-bold mt-1.5 ${toneColor}`}>
        {err ? "—" : value ?? "…"}
      </div>
    </div>
  );
}
