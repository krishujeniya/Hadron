"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FindingsByAgent } from "@/components/AgentFindingCard";
import { DiffViewer } from "@/components/DiffViewer";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { ExecutiveReviewSummary } from "@/components/ExecutiveReviewSummary";
import { Empty } from "@/components/Empty";
import { api } from "@/lib/api";
import type { ReviewDetail } from "@/lib/types";

export default function ReviewDetailPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const [copyStatus, setCopyStatus] = useState("");
  const [activeView, setActiveView] = useState<"findings" | "diff">("findings");
  const { data, error, isLoading, mutate } = useSWR<ReviewDetail>(["review-detail", id], () => api.getReview(id), { refreshInterval: (review) => review && ["completed", "failed", "escalated"].includes(review.status) ? 0 : 5000 });
  if (error) return <div role="alert" className="rounded-xl border border-border bg-panel p-6 space-y-3"><h1 className="text-xl font-semibold">Review could not be loaded</h1><p className="text-sm text-muted">Check your connection or return to the review list.</p><div className="flex gap-4"><button onClick={() => void mutate()} className="min-h-11 rounded-lg border border-border px-4 text-sm">Try again</button><Link href="/reviews" className="inline-flex min-h-11 items-center text-sm underline">Back to reviews</Link></div></div>;
  if (isLoading || !data) return <Empty><span role="status">Loading review…</span></Empty>;
  const review = data;
  async function copyMarkdown() {
    const findings = review.findings.map((finding) => `### ${finding.severity}: ${finding.summary}\n${finding.file_path || "General"}${finding.line_start ? `:${finding.line_start}` : ""}\n${finding.suggestion || ""}`).join("\n\n");
    const markdown = `# ${review.repo_full_name} #${review.pr_number}\n\n${review.pr_title}\n\nStatus: ${review.status}\nRecommendation: ${review.verdict || "Not available"}\nCommit: ${review.head_commit_sha}\n\n${findings || "No findings recorded."}\n\nAutomated findings require human assessment.`;
    try { await navigator.clipboard.writeText(markdown); setCopyStatus("Review copied to clipboard."); } catch { setCopyStatus("Clipboard access was unavailable. Select the review text to copy it manually."); }
  }
  return (
    <div className="space-y-6">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-sm text-muted"><Link href="/reviews" className="hover:text-foreground underline-offset-4 hover:underline">Reviews</Link><span aria-hidden="true">/</span><span aria-current="page">Pull request #{review.pr_number}</span></nav>
      <header className="space-y-4"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><p className="break-all font-mono text-xs text-muted">{review.repo_full_name} #{review.pr_number}</p><h1 className="mt-2 break-words text-2xl font-semibold tracking-tight sm:text-3xl">{review.pr_title || "Pull request review"}</h1></div><ReviewStatusBadge status={review.status} /></div><div className="flex flex-wrap items-center gap-x-4 gap-y-2"><span className="flex items-center gap-2 text-xs text-muted">Recommendation <VerdictChip verdict={review.verdict} /></span><a href={`https://github.com/${review.repo_full_name}/pull/${review.pr_number}`} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4">Open on GitHub <span className="sr-only">(opens in a new tab)</span><span aria-hidden="true" className="ml-1">↗</span></a><button onClick={() => void copyMarkdown()} className="min-h-11 rounded-lg border border-border bg-panel px-3 text-sm hover:bg-surface">Copy review</button></div><p role="status" className="text-xs text-muted">{copyStatus}</p></header>
      <ExecutiveReviewSummary data={review} />
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3"><div role="group" aria-label="Review view" className="flex gap-2"><button onClick={() => setActiveView("findings")} aria-pressed={activeView === "findings"} className={`min-h-11 rounded-lg px-4 text-sm font-medium ${activeView === "findings" ? "bg-surface text-foreground" : "text-muted hover:bg-surface"}`}>Findings ({review.findings.length})</button><button onClick={() => setActiveView("diff")} aria-pressed={activeView === "diff"} className={`min-h-11 rounded-lg px-4 text-sm font-medium ${activeView === "diff" ? "bg-surface text-foreground" : "text-muted hover:bg-surface"}`}>Code changes</button></div><span className="text-xs text-muted">Model confidence: {Number.isFinite(review.overall_confidence) ? `${Math.round(review.overall_confidence! * 100)}%` : "Not available"}</span></div>
      <p className="text-xs text-muted">Confidence is a model estimate, not a measured probability of correctness.</p>
      {activeView === "findings" ? <FindingsByAgent findings={review.findings ?? []} /> : <DiffViewer diff={review.pr_diff || undefined} findings={review.findings ?? []} />}
      <details className="rounded-xl border border-border bg-panel"><summary className="cursor-pointer px-5 py-4 text-sm text-muted">Review details</summary><dl className="space-y-3 border-t border-border p-5 text-xs"><div><dt className="text-muted">Commit</dt><dd className="mt-1 break-all font-mono">{review.head_commit_sha}</dd></div><div><dt className="text-muted">Review ID</dt><dd className="mt-1 break-all font-mono">{review.id}</dd></div><div><dt className="text-muted">Updated</dt><dd className="mt-1">{new Date(review.updated_at).toLocaleString()}</dd></div></dl></details>
    </div>
  );
}
