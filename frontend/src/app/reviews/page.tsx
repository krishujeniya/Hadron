"use client";

import { Suspense } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useGitHubAccount } from "@/lib/githubContext";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import type { Paginated, ReviewSummary } from "@/lib/types";

function ReviewsContent() {
  const { currentAccount, openAccountModal } = useGitHubAccount();
  const searchParams = useSearchParams();
  const repoFilter = searchParams.get("repo");

  const accountParam = currentAccount ? `&account=${encodeURIComponent(currentAccount.login)}` : "";
  const repoParam = repoFilter ? `&repo=${encodeURIComponent(repoFilter)}` : "";

  const { data, error, isLoading } =
    useSWR<Paginated<ReviewSummary>>(`/api/v1/reviews?limit=100${accountParam}${repoParam}`);

  const rawItems = data?.items ?? [];
  const items = currentAccount
    ? rawItems.filter((r) => r.repo_full_name.toLowerCase().startsWith(`${currentAccount.login.toLowerCase()}/`))
    : rawItems;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold">Reviews</h1>
            {currentAccount && (
              <span className="font-mono text-xs text-accent bg-accent/10 border border-accent/20 px-2 py-0.5 rounded-full">
                @{currentAccount.login}
              </span>
            )}
          </div>
          <p className="text-muted text-sm mt-1">
            {currentAccount
              ? `PR reviews handled by Hadron for @${currentAccount.login}'s repositories.`
              : "All PR reviews handled by Hadron."}{" "}
            {data ? `(${items.length} total)` : ""}
          </p>
        </div>

        {repoFilter && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted font-mono">Filtered by: {repoFilter}</span>
            <Link
              href="/reviews"
              className="text-xs text-accent hover:underline font-mono"
            >
              Clear filter ✕
            </Link>
          </div>
        )}
      </div>

      {error ? (
        <Empty>Failed to load: {error.message}</Empty>
      ) : isLoading ? (
        <Empty>Loading…</Empty>
      ) : items.length === 0 ? (
        <Empty>
          {currentAccount ? (
            <div className="space-y-2">
              <p>No reviews found for @{currentAccount.login}.</p>
              <p className="text-xs text-muted">
                Open a Pull Request on any of @{currentAccount.login}'s repositories to fire the review agent.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <p>No reviews yet.</p>
              <button
                onClick={openAccountModal}
                className="text-accent underline text-xs"
              >
                Connect a GitHub account
              </button>
            </div>
          )}
        </Empty>
      ) : (
        <div className="border border-border rounded-lg bg-panel overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-bg text-muted text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-2">Repo / PR</th>
                <th className="text-left px-4 py-2">Commit</th>
                <th className="text-left px-4 py-2">Findings</th>
                <th className="text-left px-4 py-2">Verdict</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-left px-4 py-2">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {items.map((r) => (
                <tr key={r.id} className="hover:bg-bg">
                  <td className="px-4 py-3 font-mono">
                    <Link
                      href={`/reviews/${encodeURIComponent(r.id)}`}
                      className="text-accent hover:underline"
                    >
                      {r.repo_full_name} #{r.pr_number}
                    </Link>
                    <div className="text-xs text-muted truncate max-w-xs">
                      {r.pr_title}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-muted">
                    {r.head_commit_sha?.slice(0, 7)}
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {r.finding_count}
                  </td>
                  <td className="px-4 py-3">
                    <VerdictChip verdict={r.verdict} />
                  </td>
                  <td className="px-4 py-3">
                    <ReviewStatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted font-mono">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function ReviewsPage() {
  return (
    <Suspense fallback={<Empty>Loading reviews...</Empty>}>
      <ReviewsContent />
    </Suspense>
  );
}
