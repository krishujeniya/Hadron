"use client";

import { Suspense } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useGitHubAccount } from "@/features/auth/github-context";
import { Empty } from "@/components/ui/Empty";
import { VerdictChip } from "@/features/reviews/VerdictChip";
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
        tag={currentAccount ? `Workspace @${currentAccount.login}` : "Human governance"}
        title="Human review queue"
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
        <svg className="w-4 h-4 text-accent shrink-0 mt-0.5 sm:mt-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
        <div>
          <span className="font-semibold text-foreground">Governance policy: </span>
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
          <div className="w-10 h-10 rounded-xl bg-panel border border-border flex items-center justify-center mx-auto text-muted" aria-hidden="true">
            <svg className="w-5 h-5 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
              <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
              <path d="m9 14 2 2 4-4" />
            </svg>
          </div>
          <h3 className="text-base font-semibold text-foreground font-sans">
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
          <div className="border border-border rounded-2xl bg-surface divide-y divide-border overflow-hidden shadow-sm min-w-0 max-w-full">
            {pending.map((h) => (
              <Link
                key={h.id}
                href={`/hitl/${encodeURIComponent(h.id)}`}
                className="flex flex-col sm:flex-row sm:items-start justify-between px-4 sm:px-5 py-3.5 sm:py-4 hover:bg-panel transition-colors gap-3 sm:gap-4 group min-w-0 max-w-full overflow-hidden"
              >
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2 min-w-0">
                    <span className="font-mono text-sm font-semibold text-foreground group-hover:text-accent group-hover:underline break-all">
                      {h.repo_full_name} #{h.pr_number}
                    </span>
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-warn/10 text-warn border border-warn/30 shrink-0">
                      Needs sign-off
                    </span>
                  </div>
                  <div className="text-sm text-foreground/90 leading-snug break-words">
                    {h.escalation_reason}
                  </div>
                  <div className="text-xs text-muted font-mono flex flex-wrap items-center gap-2 min-w-0">
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

                <div className="shrink-0 flex flex-wrap items-center gap-2 sm:gap-3 pt-1 sm:pt-0 min-w-0">
                  <VerdictChip verdict={h.agent_verdict} />
                  <span className="text-xs font-medium text-accent group-hover:translate-x-0.5 transition-transform">
                    Inspect and decide →
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
