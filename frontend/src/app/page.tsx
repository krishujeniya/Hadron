"use client";

import useSWR from "swr";
import Link from "next/link";
import { useGitHubAccount } from "@/lib/githubContext";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import type { HITLItem, Paginated, ReviewSummary } from "@/lib/types";

export default function DashboardPage() {
  const { currentAccount, repositories, openAccountModal } = useGitHubAccount();

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
        <div className="border border-border/80 rounded-xl bg-gradient-to-r from-panel via-panel to-accent/5 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {currentAccount.avatar_url ? (
              <img
                src={currentAccount.avatar_url}
                alt={currentAccount.login}
                className="w-10 h-10 rounded-full border border-border"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold">
                {currentAccount.login.slice(0, 2).toUpperCase()}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">Project Scope:</span>
                <span className="font-mono text-accent font-medium">@{currentAccount.login}</span>
                <span className="px-1.5 py-0.2 rounded text-[10px] bg-ok/10 text-ok border border-ok/20">
                  active
                </span>
              </div>
              <p className="text-muted text-xs mt-0.5">
                Monitoring {repositories.length} repositories for @{currentAccount.login}. Hadron is actively watching this account for incoming pull requests.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/repositories"
              className="px-3 py-1.5 bg-panel border border-border hover:border-accent text-xs font-mono text-muted hover:text-white rounded-lg transition"
            >
              Browse Repos ({repositories.length})
            </Link>
            <button
              onClick={openAccountModal}
              className="px-3 py-1.5 bg-accent/15 border border-accent/30 text-accent hover:bg-accent/25 text-xs font-medium rounded-lg transition"
            >
              Switch Account
            </button>
          </div>
        </div>
      ) : null}

      {/* Title */}
      <div>
        <h1 className="text-2xl font-semibold">Hadron Overview</h1>
        <p className="text-muted text-sm mt-1">
          Autonomous multi-agent pull request review engine. Polls every 5s.
        </p>
      </div>

      {/* Stats Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Reviews" value={reviews.length} err={!!reviewsErr} />
        <Stat
          label="Watched Repos"
          value={repositories.length}
          tone="ok"
        />
        <Stat
          label="HITL pending"
          value={pendingHitl.length}
          err={!!hitlErr}
          tone={pendingHitl.length > 0 ? "warn" : "ok"}
        />
        <Stat
          label="Needs human review"
          value={escalated}
          err={!!reviewsErr}
          tone={escalated > 0 ? "warn" : "ok"}
        />
      </section>

      {/* Recent Reviews */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-medium">Recent reviews</h2>
            {currentAccount && (
              <span className="text-xs text-muted font-mono">
                (@{currentAccount.login})
              </span>
            )}
          </div>
          <Link href="/reviews" className="text-sm text-accent hover:underline">
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
          <div className="border border-border rounded-lg bg-panel divide-y divide-border">
            {recent.map((r) => (
              <Link
                key={r.id}
                href={`/reviews/${encodeURIComponent(r.id)}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-bg gap-3"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm truncate text-white">
                    {r.repo_full_name} #{r.pr_number}
                  </div>
                  <div className="text-xs text-muted truncate mt-0.5">
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

      {/* HITL Queue */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-medium">HITL queue</h2>
          <Link href="/hitl" className="text-sm text-accent hover:underline">
            Open queue →
          </Link>
        </div>
        {pendingHitl.length === 0 ? (
          <Empty>Queue is clear.</Empty>
        ) : (
          <div className="border border-border rounded-lg bg-panel divide-y divide-border">
            {pendingHitl.slice(0, 5).map((h) => (
              <Link
                key={h.id}
                href={`/hitl/${encodeURIComponent(h.id)}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-bg gap-3"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm truncate">
                    {h.repo_full_name} #{h.pr_number}
                  </div>
                  <div className="text-xs text-muted truncate">
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
  const color =
    tone === "warn"
      ? "text-warn"
      : tone === "err"
      ? "text-err"
      : tone === "ok"
      ? "text-ok"
      : "text-white";
  return (
    <div className="border border-border rounded-lg bg-panel px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className={`text-2xl font-mono mt-1 ${color}`}>
        {err ? "—" : value ?? "…"}
      </div>
    </div>
  );
}
