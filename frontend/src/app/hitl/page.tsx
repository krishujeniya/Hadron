"use client";

import { Suspense } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useGitHubAccount } from "@/lib/githubContext";
import { Empty } from "@/components/Empty";
import { VerdictChip } from "@/components/VerdictChip";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import type { HITLItem, Paginated } from "@/lib/types";

const PAGE_SIZE = 25;

function HITLQueueContent() {
  const { currentAccount } = useGitHubAccount();
  const searchParams = useSearchParams();
  const router = useRouter();

  const rawPage = Number(searchParams.get("page") || 1);
  const page = Number.isSafeInteger(rawPage) && rawPage > 0 ? Math.min(rawPage, 1000000) : 1;

  const queryParams = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String((page - 1) * PAGE_SIZE),
  });
  if (currentAccount) {
    queryParams.set("account", currentAccount.login);
  }

  const { data, error, isLoading, mutate } = useSWR<Paginated<HITLItem>>(
    `/api/v1/hitl/queue?${queryParams.toString()}`
  );

  const items = data?.items ?? [];
  const pending = items.filter((h) => h.status === "pending" || h.status === "in_review");
  const totalCount = data?.total ?? pending.length;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE) || 1;

  const pageUrl = (nextPage: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(nextPage));
    return `/hitl?${params.toString()}`;
  };

  return (
    <div className="space-y-6">
      {/* Header & Context */}
      <PageHeader
        tag={currentAccount ? `Workspace @${currentAccount.login}` : "Human Governance"}
        title="Human Review & Sign-Offs"
        description={
          currentAccount
            ? `Pull requests escalated for human determination in workspace @${currentAccount.login}.`
            : "Pull requests escalated for human review across connected repositories."
        }
        actions={
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-panel border border-border text-xs font-mono text-foreground">
            <span
              className={`w-2 h-2 rounded-full ${totalCount > 0 ? "bg-warn" : "bg-ok"}`}
              aria-hidden="true"
            />
            <span>
              {totalCount} pending determination{totalCount === 1 ? "" : "s"}
            </span>
          </div>
        }
      />

      {/* Governance Banner */}
      <div className="p-4 rounded-xl border border-border bg-panel flex items-start sm:items-center gap-3 text-xs text-foreground">
        <span className="text-base shrink-0" aria-hidden="true">
          🛡️
        </span>
        <div>
          <span className="font-semibold text-foreground">Consequential Governance Gate: </span>
          Decisions recorded here represent binding human determinations. Approved, rejected, or
          dismissed actions are permanently attributed to your authenticated identity in the audit ledger
          and posted to GitHub. Submitting does not merge the pull request.
        </div>
      </div>

      {error ? (
        <div role="alert" className="rounded-xl border border-err/30 bg-err/10 p-6 space-y-3">
          <h2 className="font-medium text-foreground">Failed to load human review queue</h2>
          <p className="text-xs text-muted">{error.message || "A network or server error occurred."}</p>
          <Button variant="outline" size="sm" onClick={() => void mutate()}>
            Retry
          </Button>
        </div>
      ) : isLoading ? (
        <Empty>
          <span role="status" className="text-muted">Loading pending reviews…</span>
        </Empty>
      ) : pending.length === 0 ? (
        <div className="border border-border rounded-2xl bg-surface p-8 text-center space-y-3 shadow-sm">
          <div className="text-2xl" aria-hidden="true">
            📋
          </div>
          <h3 className="text-base font-semibold text-foreground font-mono">
            No Pending Decisions in Scope
          </h3>
          <p className="text-xs text-muted max-w-md mx-auto">
            There are currently no pull requests awaiting human review in this workspace. An empty queue
            means there are no active escalations requiring manual review; automated checks and review
            policies may still apply.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="border border-border rounded-2xl bg-surface divide-y divide-border overflow-hidden shadow-sm">
            {pending.map((h) => (
              <Link
                key={h.id}
                href={`/hitl/${encodeURIComponent(h.id)}`}
                className="flex flex-col sm:flex-row sm:items-start justify-between px-5 py-4 hover:bg-panel transition-all gap-4 group"
              >
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-foreground group-hover:text-accent group-hover:underline">
                      {h.repo_full_name} #{h.pr_number}
                    </span>
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-warn/10 text-warn border border-warn/30">
                      Needs Sign-Off
                    </span>
                  </div>
                  <div className="text-sm text-foreground/90 leading-snug break-words">
                    {h.escalation_reason}
                  </div>
                  <div className="text-xs text-muted font-mono flex flex-wrap items-center gap-2">
                    <span>
                      Model confidence:{" "}
                      {Number.isFinite(h.overall_confidence)
                        ? `${Math.round(h.overall_confidence * 100)}%`
                        : "Not available"}
                    </span>
                    <span>•</span>
                    <time dateTime={h.created_at}>
                      Escalated {new Date(h.created_at).toLocaleDateString()}
                    </time>
                  </div>
                </div>

                <div className="shrink-0 flex items-center gap-3 pt-1 sm:pt-0">
                  <VerdictChip verdict={h.agent_verdict} />
                  <span className="text-xs font-medium text-accent group-hover:translate-x-0.5 transition-transform">
                    Inspect & Decide →
                  </span>
                </div>
              </Link>
            ))}
          </div>

          {/* Pagination Navigation */}
          {totalPages > 1 && (
            <nav
              aria-label="Queue pagination"
              className="flex items-center justify-between rounded-xl border border-border bg-panel p-4 text-xs"
            >
              <span className="text-muted">
                Page <strong className="text-foreground">{page}</strong> of{" "}
                <strong className="text-foreground">{totalPages}</strong> ({totalCount} total)
              </span>
              <div className="flex items-center gap-2">
                {page > 1 && (
                  <Link
                    href={pageUrl(page - 1)}
                    className="inline-flex min-h-8 items-center rounded-lg border border-border bg-surface px-3 font-medium text-foreground hover:bg-raised"
                  >
                    Previous
                  </Link>
                )}
                {page < totalPages && (
                  <Link
                    href={pageUrl(page + 1)}
                    className="inline-flex min-h-8 items-center rounded-lg border border-border bg-surface px-3 font-medium text-foreground hover:bg-raised"
                  >
                    Next
                  </Link>
                )}
              </div>
            </nav>
          )}
        </div>
      )}
    </div>
  );
}

export default function HITLQueuePage() {
  return (
    <Suspense fallback={<Empty>Loading pending determinations…</Empty>}>
      <HITLQueueContent />
    </Suspense>
  );
}
