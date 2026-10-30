"use client";

import { Suspense } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useGitHubAccount } from "@/lib/githubContext";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import type { Paginated, ReviewSummary } from "@/lib/types";

const PAGE_SIZE = 25;
function ReviewsContent() {
  const { currentAccount } = useGitHubAccount();
  const searchParams = useSearchParams();
  const router = useRouter();
  const repo = searchParams.get("repo") || "";
  const status = searchParams.get("status") || "";
  const rawPage = Number(searchParams.get("page") || 1);
  const page = Number.isSafeInteger(rawPage) && rawPage > 0 ? Math.min(rawPage, 1000000) : 1;
  const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
  if (currentAccount) query.set("account", currentAccount.login);
  if (repo) query.set("repo", repo);
  if (status) query.set("status", status);
  const { data, error, isLoading, mutate } = useSWR<Paginated<ReviewSummary>>(currentAccount ? `/api/v1/reviews?${query}` : null);
  const items = (data?.items ?? []).filter((item) => item.repo_full_name.toLowerCase().startsWith(`${currentAccount?.login.toLowerCase()}/`));
  const pageUrl = (nextPage: number) => { const params = new URLSearchParams(searchParams.toString()); params.set("page", String(nextPage)); return `/reviews?${params}`; };

  return (
    <div className="space-y-6">
      <header><p className="text-xs font-medium uppercase tracking-widest text-muted">Workspace</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Reviews</h1><p className="mt-2 text-sm text-muted">Track pull requests, inspect findings, and see what needs attention.</p></header>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <label htmlFor="review-status" className="mb-2 block text-xs font-medium text-muted">
            Review status
          </label>
          <select
            id="review-status"
            name="status"
            value={status}
            onChange={(event) => {
              const params = new URLSearchParams(searchParams.toString());
              params.delete("page");
              if (event.target.value) params.set("status", event.target.value);
              else params.delete("status");
              router.push(`/reviews?${params}`);
            }}
            className="min-h-11 rounded-lg border border-border bg-panel px-3 text-sm"
          >
            <option value="">All statuses</option>
            <option value="queued">Queued</option>
            <option value="in_progress">In progress</option>
            <option value="agents_running">Reviewing</option>
            <option value="aggregating">Combining findings</option>
            <option value="posting">Posting review</option>
            <option value="completed">Completed</option>
            <option value="escalated">Needs review</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        {repo && <p className="text-sm text-muted break-all">Repository: <span className="font-mono text-foreground">{repo}</span> <Link href="/reviews" className="ml-2 inline-flex min-h-11 items-center underline underline-offset-4">Clear filters</Link></p>}
        {data && !error && <p className="text-xs text-muted">{new Intl.NumberFormat().format(data.total)} matching reviews</p>}
      </div>
      {error ? <div role="alert" className="rounded-xl border border-border bg-panel p-6"><h2 className="font-medium">Reviews could not be loaded</h2><p className="mt-2 text-sm text-muted">Check your connection and try again.</p><button onClick={() => void mutate()} className="mt-3 min-h-11 rounded-lg border border-border px-4 text-sm hover:bg-surface">Try again</button></div> : isLoading ? <Empty><span role="status">Loading reviews…</span></Empty> : items.length === 0 ? <Empty><div className="space-y-2"><h2 className="font-medium text-foreground">{status || repo ? "No reviews match these filters" : page > 1 ? "No reviews on this page" : "No reviews yet"}</h2><p>{status || repo ? "Try another status or clear your filters." : "Reviews appear here after a connected repository sends a pull request event."}</p><Link href={status || repo || page > 1 ? "/reviews" : "/repositories"} className="inline-flex min-h-11 items-center font-medium text-accent underline underline-offset-4">{status || repo || page > 1 ? "Reset filters and pagination" : "View repositories"}</Link></div></Empty> : <div className="overflow-hidden rounded-xl border border-border bg-panel"><div role="region" aria-label="Pull request reviews" tabIndex={0} className="overflow-x-auto"><table className="w-full min-w-[680px] text-sm"><caption className="sr-only">Pull request reviews, page {page}</caption><thead className="border-b border-border bg-surface/50 text-xs text-muted"><tr><th scope="col" className="px-5 py-3 text-left font-medium">Pull request</th><th scope="col" className="px-4 py-3 text-left font-medium">Status</th><th scope="col" className="px-4 py-3 text-left font-medium">Recommendation</th><th scope="col" className="px-4 py-3 text-right font-medium">Findings</th><th scope="col" className="px-5 py-3 text-right font-medium">Created</th></tr></thead><tbody className="divide-y divide-border">{items.map((review) => <tr key={review.id} className="hover:bg-surface/50"><td className="max-w-sm px-5 py-4"><Link href={`/reviews/${encodeURIComponent(review.id)}`} className="font-medium text-foreground hover:underline underline-offset-4"><span className="block break-words">{review.pr_title || `Pull request #${review.pr_number}`}</span><span className="mt-1 block break-all text-xs font-normal text-muted">{review.repo_full_name} #{review.pr_number}</span></Link></td><td className="px-4 py-4"><ReviewStatusBadge status={review.status} /></td><td className="px-4 py-4"><VerdictChip verdict={review.verdict} /></td><td className="px-4 py-4 text-right tabular-nums">{review.finding_count}</td><td className="whitespace-nowrap px-5 py-4 text-right text-xs text-muted"><time dateTime={review.created_at}>{new Date(review.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</time></td></tr>)}</tbody></table></div></div>}
      {data && !error && (page > 1 || data.total > PAGE_SIZE) && <nav aria-label="Review pages" className="flex items-center justify-between gap-3 text-sm"><span className="text-muted">Page {page}</span><div className="flex gap-2">{page > 1 && <Link href={pageUrl(page - 1)} className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 hover:bg-surface">Previous</Link>}{page * PAGE_SIZE < data.total && <Link href={pageUrl(page + 1)} className="inline-flex min-h-11 items-center rounded-lg border border-border px-4 hover:bg-surface">Next</Link>}</div></nav>}
    </div>
  );
}
export default function ReviewsPage() { return <Suspense fallback={<Empty>Loading reviews…</Empty>}><ReviewsContent /></Suspense>; }
