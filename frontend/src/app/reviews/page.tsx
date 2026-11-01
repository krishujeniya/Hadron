"use client";

import { Suspense, useState, useEffect, useTransition } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useGitHubAccount } from "@/lib/githubContext";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import type { Paginated, ReviewSummary } from "@/lib/types";

const PAGE_SIZE = 25;

function ReviewsContent() {
  const { currentAccount, openAccountModal, logout } = useGitHubAccount();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [, startTransition] = useTransition();

  const repo = searchParams.get("repo") || "";
  const status = searchParams.get("status") || "";
  const qParam = searchParams.get("q") || "";
  const sort = searchParams.get("sort") || "newest";

  const rawPage = Number(searchParams.get("page") || 1);
  const page = Number.isSafeInteger(rawPage) && rawPage > 0 ? Math.min(rawPage, 1000000) : 1;

  // Local state for debounced search input
  const [searchInput, setSearchInput] = useState(qParam);

  // Synchronize local input state if URL param changes externally (e.g., Back/Forward navigation)
  useEffect(() => {
    setSearchInput(qParam);
  }, [qParam]);

  // Debounce search update to URL
  useEffect(() => {
    const handler = setTimeout(() => {
      if (searchInput !== qParam) {
        const params = new URLSearchParams(searchParams.toString());
        params.delete("page");
        if (searchInput.trim()) {
          params.set("q", searchInput.trim());
        } else {
          params.delete("q");
        }
        startTransition(() => {
          router.replace(`/reviews?${params.toString()}`);
        });
      }
    }, 350);

    return () => clearTimeout(handler);
  }, [searchInput, qParam, searchParams, router]);

  // Build SWR query params
  const query = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String((page - 1) * PAGE_SIZE),
    sort,
  });
  if (currentAccount) query.set("account", currentAccount.login);
  if (repo) query.set("repo", repo);
  if (status) query.set("status", status);
  if (qParam.trim()) query.set("q", qParam.trim());

  const { data, error, isLoading, mutate } = useSWR<Paginated<ReviewSummary>>(
    currentAccount ? `/api/v1/reviews?${query.toString()}` : null
  );

  const items = (data?.items ?? []).filter((item) =>
    item.repo_full_name.toLowerCase().startsWith(`${currentAccount?.login.toLowerCase()}/`)
  );

  const totalReviews = data?.total ?? 0;
  const totalPages = Math.ceil(totalReviews / PAGE_SIZE) || 1;
  const isPageOutOfBounds = totalReviews > 0 && page > totalPages;

  const hasActiveFilters = Boolean(repo || status || qParam.trim() || sort !== "newest");

  const updateParam = (key: string, value: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("page");
    if (value && value.trim()) {
      params.set(key, value.trim());
    } else {
      params.delete(key);
    }
    router.push(`/reviews?${params.toString()}`);
  };

  const clearAllFilters = () => {
    setSearchInput("");
    router.push("/reviews");
  };

  const pageUrl = (nextPage: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(nextPage));
    return `/reviews?${params.toString()}`;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reviews"
        tag="Workspace"
        description="Track pull requests, inspect findings, and review security and reliability assessments."
      />

      {/* Controls & Filter Bar */}
      <div className="flex flex-col gap-4 rounded-xl border border-border bg-panel p-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-end">
          {/* Search box with clear button */}
          <div className="w-full sm:max-w-xs">
            <label htmlFor="review-search" className="mb-1.5 block text-xs font-medium text-muted">
              Search reviews
            </label>
            <div className="relative">
              <input
                id="review-search"
                type="text"
                placeholder="Title, commit SHA, repo…"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
              {searchInput && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchInput("");
                    updateParam("q", null);
                  }}
                  aria-label="Clear search query"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-foreground text-xs"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Status selector */}
          <div className="w-full sm:w-44">
            <label htmlFor="review-status" className="mb-1.5 block text-xs font-medium text-muted">
              Status
            </label>
            <select
              id="review-status"
              name="status"
              value={status}
              onChange={(e) => updateParam("status", e.target.value || null)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <option value="">All statuses</option>
              <option value="queued">Queued</option>
              <option value="in_progress">In progress</option>
              <option value="agents_running">Reviewing</option>
              <option value="aggregating">Combining findings</option>
              <option value="posting">Posting review</option>
              <option value="completed">Completed</option>
              <option value="escalated">Needs human review</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {/* Sort selector */}
          <div className="w-full sm:w-40">
            <label htmlFor="review-sort" className="mb-1.5 block text-xs font-medium text-muted">
              Sort by
            </label>
            <select
              id="review-sort"
              name="sort"
              value={sort}
              onChange={(e) => updateParam("sort", e.target.value || null)}
              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="findings">Most findings</option>
            </select>
          </div>
        </div>

        {/* Filter clear & matching count */}
        <div className="flex flex-wrap items-center justify-between gap-3 sm:justify-end">
          {hasActiveFilters && (
            <Button
              variant="outline"
              size="sm"
              onClick={clearAllFilters}
              className="text-xs"
            >
              Clear all filters
            </Button>
          )}

          {data && !error && (
            <p className="text-xs text-muted" aria-live="polite">
              <span className="font-semibold text-foreground">
                {new Intl.NumberFormat().format(data.total)}
              </span>{" "}
              {data.total === 1 ? "review" : "reviews"} found
            </p>
          )}
        </div>
      </div>

      {/* Active Repo Filter Notification */}
      {repo && (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-panel px-4 py-2.5 text-xs text-muted">
          <span>
            Filtered to repository: <span className="font-mono font-medium text-foreground">{repo}</span>
          </span>
          <button
            onClick={() => updateParam("repo", null)}
            className="font-medium text-accent hover:underline underline-offset-4"
          >
            Remove filter
          </button>
        </div>
      )}

      {/* Main Content Area */}
      {error ? (
        <div role="alert" className="rounded-xl border border-err/30 bg-err/10 p-6 space-y-4">
          <div>
            <h2 className="font-semibold text-foreground text-base">
              {error.status === 401 || error.status === 403
                ? "Authentication Required"
                : error.status === 503
                ? "Review Database Temporarily Unavailable"
                : "Reviews could not be loaded"}
            </h2>
            <p className="mt-1.5 text-sm text-muted">
              {error.status === 401 || error.status === 403
                ? `Your session has expired or requires authentication to load reviews for ${
                    currentAccount ? `@${currentAccount.login}` : "this account"
                  }. Sign in or select your GitHub account to continue.`
                : error.status === 503
                ? "The review database service is temporarily reconnecting. Please retry in a few moments."
                : error.message || "There was a problem contacting the review service. Check your connection or authentication."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {error.status === 401 || error.status === 403 ? (
              <>
                <Button size="sm" onClick={() => openAccountModal()}>
                  Sign in or Reconnect
                </Button>
                <Button variant="outline" size="sm" onClick={() => void mutate()}>
                  Try again
                </Button>
                <Button variant="ghost" size="sm" onClick={() => void logout()}>
                  Switch Account
                </Button>
              </>
            ) : error.status === 503 ? (
              <>
                <Button size="sm" onClick={() => void mutate()}>
                  Retry connection
                </Button>
                <Button variant="outline" size="sm" onClick={() => router.push("/health")}>
                  Check Service Health
                </Button>
              </>
            ) : (
              <>
                <Button size="sm" onClick={() => void mutate()}>
                  Try again
                </Button>
                <Button variant="outline" size="sm" onClick={() => openAccountModal()}>
                  Reconnect Account
                </Button>
              </>
            )}
          </div>
        </div>
      ) : isLoading ? (
        <Empty>
          <span role="status" className="text-muted">Loading reviews…</span>
        </Empty>
      ) : isPageOutOfBounds ? (
        <Empty>
          <div className="space-y-3">
            <h2 className="font-medium text-foreground">Page out of range</h2>
            <p className="text-sm text-muted">
              Page {page} exceeds the {totalPages} available page{totalPages === 1 ? "" : "s"} of results.
            </p>
            <Button size="sm" onClick={() => router.push(pageUrl(1))}>
              Go to first page
            </Button>
          </div>
        </Empty>
      ) : items.length === 0 ? (
        <Empty>
          <div className="space-y-2">
            <h2 className="font-medium text-foreground">
              {hasActiveFilters ? "No reviews match your filters" : "No reviews yet"}
            </h2>
            <p className="text-sm text-muted">
              {hasActiveFilters
                ? "Try searching for a different term, changing status, or clearing your filters."
                : "Reviews appear here after a connected repository sends a pull request webhook."}
            </p>
            {hasActiveFilters ? (
              <Button variant="outline" size="sm" onClick={clearAllFilters} className="mt-2">
                Clear filters
              </Button>
            ) : (
              <Link
                href="/repositories"
                className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-4"
              >
                View connected repositories
              </Link>
            )}
          </div>
        </Empty>
      ) : (
        <div className="space-y-4">
          {/* Desktop Table View (Hidden on mobile) */}
          <div className="hidden sm:block overflow-hidden rounded-xl border border-border bg-panel">
            <div
              role="region"
              aria-label="Pull request reviews"
              tabIndex={0}
              className="overflow-x-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <table className="w-full min-w-[700px] text-sm">
                <caption className="sr-only">
                  Pull request reviews, page {page} of {totalPages}
                </caption>
                <thead className="border-b border-border bg-surface/50 text-xs text-muted">
                  <tr>
                    <th scope="col" className="px-5 py-3 text-left font-medium">Pull request</th>
                    <th scope="col" className="px-4 py-3 text-left font-medium">Status</th>
                    <th scope="col" className="px-4 py-3 text-left font-medium">Recommendation</th>
                    <th scope="col" className="px-4 py-3 text-right font-medium">Findings</th>
                    <th scope="col" className="px-5 py-3 text-right font-medium">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {items.map((review) => (
                    <tr key={review.id} className="hover:bg-surface/50 transition-colors">
                      <td className="max-w-md px-5 py-4">
                        <Link
                          href={`/reviews/${encodeURIComponent(review.id)}`}
                          className="font-medium text-foreground hover:underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
                        >
                          <span className="block break-words">{review.pr_title || `Pull request #${review.pr_number}`}</span>
                          <span className="mt-1 block break-all text-xs font-normal text-muted">
                            {review.repo_full_name} #{review.pr_number} • <span className="font-mono">{review.head_commit_sha.slice(0, 7)}</span>
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <ReviewStatusBadge status={review.status} />
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <VerdictChip verdict={review.verdict} />
                      </td>
                      <td className="px-4 py-4 text-right tabular-nums text-foreground font-medium">
                        {review.finding_count}
                      </td>
                      <td className="whitespace-nowrap px-5 py-4 text-right text-xs text-muted">
                        <time dateTime={review.created_at}>
                          {new Date(review.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </time>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile Card View (Shown only on small screens, no horizontal overflow) */}
          <div className="sm:hidden space-y-3">
            {items.map((review) => (
              <div
                key={review.id}
                className="rounded-xl border border-border bg-panel p-4 space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-xs font-mono text-muted break-all">
                      {review.repo_full_name} #{review.pr_number}
                    </p>
                    <Link
                      href={`/reviews/${encodeURIComponent(review.id)}`}
                      className="mt-1 block font-medium text-foreground hover:underline underline-offset-4 break-words"
                    >
                      {review.pr_title || `Pull request #${review.pr_number}`}
                    </Link>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border">
                  <ReviewStatusBadge status={review.status} />
                  <VerdictChip verdict={review.verdict} />
                  <span className="text-xs text-muted tabular-nums ml-auto">
                    {review.finding_count} {review.finding_count === 1 ? "finding" : "findings"}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs text-muted pt-2 border-t border-border">
                  <time dateTime={review.created_at}>
                    {new Date(review.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </time>
                  <Link
                    href={`/reviews/${encodeURIComponent(review.id)}`}
                    className="font-medium text-accent hover:underline underline-offset-4"
                  >
                    Inspect review →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pagination Navigation */}
      {data && !error && totalReviews > 0 && (totalPages > 1 || page > 1) && (
        <nav
          aria-label="Review pagination"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-panel p-4 text-sm"
        >
          <span className="text-xs text-muted">
            Page <span className="font-semibold text-foreground">{page}</span> of{" "}
            <span className="font-semibold text-foreground">{totalPages}</span>
          </span>

          <div className="flex items-center gap-2">
            {page > 1 ? (
              <Link
                href={pageUrl(page - 1)}
                className="inline-flex min-h-9 items-center rounded-lg border border-border bg-surface px-3 text-xs font-medium text-foreground hover:bg-raised transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                Previous
              </Link>
            ) : (
              <span className="inline-flex min-h-9 items-center rounded-lg border border-border/50 bg-surface/50 px-3 text-xs font-medium text-muted/50 cursor-not-allowed">
                Previous
              </span>
            )}

            {page < totalPages ? (
              <Link
                href={pageUrl(page + 1)}
                className="inline-flex min-h-9 items-center rounded-lg border border-border bg-surface px-3 text-xs font-medium text-foreground hover:bg-raised transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                Next
              </Link>
            ) : (
              <span className="inline-flex min-h-9 items-center rounded-lg border border-border/50 bg-surface/50 px-3 text-xs font-medium text-muted/50 cursor-not-allowed">
                Next
              </span>
            )}
          </div>
        </nav>
      )}
    </div>
  );
}

export default function ReviewsPage() {
  return (
    <Suspense fallback={<Empty>Loading reviews…</Empty>}>
      <ReviewsContent />
    </Suspense>
  );
}
