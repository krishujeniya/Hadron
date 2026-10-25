"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useGitHubAccount } from "@/lib/githubContext";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import { ExecutiveHealthScore } from "@/components/ExecutiveHealthScore";
import { PlainEnglishAssistant } from "@/components/PlainEnglishAssistant";
import { NonTechReviewCard } from "@/components/NonTechReviewCard";
import type { HITLItem, Paginated, ReviewSummary } from "@/lib/types";

export default function DashboardPage() {
  const { currentAccount, repositories, openAccountModal } = useGitHubAccount();
  const [viewMode, setViewMode] = useState<"executive" | "developer">("executive");

  // Persist non-tech preference in localStorage
  useEffect(() => {
    const saved = localStorage.getItem("hadron_view_mode");
    if (saved === "developer" || saved === "executive") {
      setViewMode(saved);
    }
  }, []);

  const setMode = (mode: "executive" | "developer") => {
    setViewMode(mode);
    localStorage.setItem("hadron_view_mode", mode);
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

  const recent = reviews.slice(0, 8);
  const pendingHitl = hitl.filter((h) => h.status === "pending" || h.status === "in_review");
  const escalated = reviews.filter((r) => r.status === "escalated" || r.needs_human_review).length;

  return (
    <div className="space-y-8">
      {/* Account Context Banner */}
      {currentAccount ? (
        <div className="border border-white/10 rounded-2xl bg-gradient-to-r from-zinc-950 via-zinc-900 to-black p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-lg shadow-black/50">
          <div className="flex items-center gap-3">
            {currentAccount.avatar_url ? (
              <img
                src={currentAccount.avatar_url}
                alt={currentAccount.login}
                className="w-10 h-10 rounded-full border border-white/20"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-white/10 text-white flex items-center justify-center font-bold">
                {currentAccount.login.slice(0, 2).toUpperCase()}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">Active Workspace:</span>
                <span className="font-mono text-white font-medium">@{currentAccount.login}</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-white/10 text-white border border-white/20">
                  Protected
                </span>
              </div>
              <p className="text-zinc-400 text-xs mt-0.5">
                Hadron is safeguarding {repositories.length} repositories for @{currentAccount.login}. All pull requests are reviewed autonomously.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/repositories"
              className="px-3 py-1.5 bg-black/60 border border-white/10 hover:border-white/30 text-xs font-mono text-zinc-300 hover:text-white rounded-xl transition"
            >
              Browse Repos ({repositories.length})
            </Link>
            <button
              onClick={openAccountModal}
              className="px-3.5 py-1.5 bg-gradient-to-b from-white to-zinc-200 text-black hover:from-zinc-100 hover:to-zinc-300 text-xs font-semibold rounded-xl transition shadow-sm shadow-white/5"
            >
              Switch Account
            </button>
          </div>
        </div>
      ) : null}

      {/* Top Header & Interactive Mode Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
            {viewMode === "executive" ? "Executive Product Command" : "Hadron Developer Overview"}
          </h1>
          <p className="text-zinc-400 text-sm mt-1">
            {viewMode === "executive"
              ? "High-level codebase health, safety guardrails, and plain-English intelligence for leaders & teams."
              : "Autonomous multi-agent pull request review engine. Real-time developer telemetries."}
          </p>
        </div>

        {/* View Mode Toggle (Executive / Non-tech vs Technical) */}
        <div className="inline-flex p-1 rounded-xl bg-black/80 border border-white/10 shadow-inner">
          <button
            type="button"
            onClick={() => setMode("executive")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
              viewMode === "executive"
                ? "bg-gradient-to-b from-white to-zinc-200 text-black shadow-md shadow-white/10"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <span>✨</span>
            <span>Plain English (Non-Tech)</span>
          </button>
          <button
            type="button"
            onClick={() => setMode("developer")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
              viewMode === "developer"
                ? "bg-gradient-to-b from-white to-zinc-200 text-black shadow-md shadow-white/10"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <span>⚡</span>
            <span>Developer View</span>
          </button>
        </div>
      </div>

      {/* EXECUTIVE / NON-TECH USER VIEW */}
      {viewMode === "executive" ? (
        <div className="space-y-8">
          {/* 1. Psychological Anchor: Visual Health Gauge & Peace-of-Mind Metrics */}
          <ExecutiveHealthScore
            reviews={reviews}
            watchedReposCount={repositories.length}
            pendingHitlCount={pendingHitl.length}
          />

          {/* 2. Interactive Plain English Assistant: Answers questions without code jargon */}
          <PlainEnglishAssistant
            recentReviews={reviews}
            accountName={currentAccount?.login}
          />

          {/* 3. Non-Tech Activity Feed: What did developers actually ship? */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <span>🚀</span> What Your Team Shipped Recently
                </h2>
                <p className="text-xs text-zinc-400">
                  Every pull request translated into plain business and product impacts.
                </p>
              </div>
              <Link href="/reviews" className="text-xs font-medium text-white hover:underline">
                View all reviews →
              </Link>
            </div>

            {reviewsErr ? (
              <Empty>Could not load reviews: {String(reviewsErr.message)}</Empty>
            ) : recent.length === 0 ? (
              <Empty>
                {currentAccount
                  ? `No reviews recorded yet for @${currentAccount.login}. When your developers open a PR, Hadron will provide an instant plain-English breakdown here.`
                  : "No reviews yet. Open a PR on any repository."}
              </Empty>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {recent.map((r) => (
                  <NonTechReviewCard key={r.id} review={r} />
                ))}
              </div>
            )}
          </section>
        </div>
      ) : (
        /* DEVELOPER TECHNICAL VIEW */
        <div className="space-y-8">
          {/* Stats Cards */}
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Stat label="Reviews" value={reviews.length} err={!!reviewsErr} />
            <Stat label="Watched Repos" value={repositories.length} tone="ok" />
            <Stat
              label="Approvals Pending"
              value={pendingHitl.length}
              err={!!hitlErr}
              tone={pendingHitl.length > 0 ? "warn" : "ok"}
            />
            <Stat
              label="Escalated Items"
              value={escalated}
              err={!!reviewsErr}
              tone={escalated > 0 ? "warn" : "ok"}
            />
          </section>

          {/* Recent Reviews Table */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-medium text-white">Recent reviews</h2>
                {currentAccount && (
                  <span className="text-xs text-zinc-400 font-mono">
                    (@{currentAccount.login})
                  </span>
                )}
              </div>
              <Link href="/reviews" className="text-sm text-white hover:underline">
                View all →
              </Link>
            </div>
            {reviewsErr ? (
              <Empty>Could not load reviews: {String(reviewsErr.message)}</Empty>
            ) : recent.length === 0 ? (
              <Empty>
                {currentAccount
                  ? `No reviews recorded yet for @${currentAccount.login}. Open a PR on any of their repositories.`
                  : "No reviews yet. Open a PR on a watched repo."}
              </Empty>
            ) : (
              <div className="border border-white/10 rounded-xl bg-panel divide-y divide-white/10 overflow-hidden shadow-sm">
                {recent.map((r) => (
                  <Link
                    key={r.id}
                    href={`/reviews/${encodeURIComponent(r.id)}`}
                    className="flex items-center justify-between px-4 py-3 hover:bg-white/[0.03] transition-colors gap-3"
                  >
                    <div className="min-w-0">
                      <div className="font-mono text-sm truncate text-white">
                        {r.repo_full_name} #{r.pr_number}
                      </div>
                      <div className="text-xs text-zinc-400 truncate mt-0.5">
                        {r.pr_title}
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

          {/* Approvals Queue Table */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-medium text-white">Approvals & Action Needed</h2>
              <Link href="/hitl" className="text-sm text-white hover:underline">
                Open queue →
              </Link>
            </div>
            {pendingHitl.length === 0 ? (
              <Empty>Queue is clear.</Empty>
            ) : (
              <div className="border border-white/10 rounded-xl bg-panel divide-y divide-white/10 overflow-hidden shadow-sm">
                {pendingHitl.slice(0, 5).map((h) => (
                  <Link
                    key={h.id}
                    href={`/hitl/${encodeURIComponent(h.id)}`}
                    className="flex items-center justify-between px-4 py-3 hover:bg-white/[0.03] transition-colors gap-3"
                  >
                    <div className="min-w-0">
                      <div className="font-mono text-sm truncate text-white">
                        {h.repo_full_name} #{h.pr_number}
                      </div>
                      <div className="text-xs text-zinc-400 truncate">
                        {h.escalation_reason}
                      </div>
                    </div>
                    <VerdictChip verdict={h.agent_verdict} />
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

function Stat({
  label,
  value,
  err,
  tone,
}: {
  label: string;
  value?: number;
  err?: boolean;
  tone?: "ok" | "warn" | "err";
}) {
  return (
    <div className="border border-white/10 rounded-xl bg-gradient-to-b from-zinc-900/60 to-black/80 px-4 py-3.5 hover:border-white/20 transition-all shadow-sm">
      <div className="text-xs uppercase tracking-wider font-mono text-zinc-400">{label}</div>
      <div className="text-2xl font-mono font-bold mt-1.5 bg-gradient-to-r from-white via-zinc-100 to-zinc-300 bg-clip-text text-transparent">
        {err ? "—" : value ?? "…"}
      </div>
    </div>
  );
}
