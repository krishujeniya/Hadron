"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { FindingsByAgent } from "@/components/AgentFindingCard";

const DiffViewer = dynamic(
  () => import("@/components/DiffViewer").then((mod) => mod.DiffViewer),
  {
    loading: () => (
      <div className="rounded-xl border border-border bg-panel p-8 text-center text-sm text-muted">
        Loading diff viewer...
      </div>
    ),
  }
);
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { ExecutiveReviewSummary } from "@/components/ExecutiveReviewSummary";
import { Empty } from "@/components/Empty";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { ReviewDetail } from "@/lib/types";

export default function ReviewDetailPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const [copyStatus, setCopyStatus] = useState("");
  const [activeView, setActiveView] = useState<"findings" | "diff">("findings");

  const { data, error, isLoading, mutate } = useSWR<ReviewDetail>(
    ["review-detail", id],
    () => api.getReview(id),
    {
      refreshInterval: (review) =>
        review && ["completed", "failed", "escalated"].includes(review.status) ? 0 : 5000,
    }
  );

  if (error) {
    return (
      <div role="alert" className="rounded-xl border border-border bg-panel p-6 space-y-3">
        <h1 className="text-xl font-semibold text-foreground">Review could not be loaded</h1>
        <p className="text-sm text-muted">Check your connection or return to the review list.</p>
        <div className="flex gap-4">
          <Button variant="outline" size="sm" onClick={() => void mutate()}>
            Try again
          </Button>
          <Link
            href="/reviews"
            className="inline-flex min-h-9 items-center text-sm font-medium text-accent underline underline-offset-4"
          >
            Back to reviews
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <Empty>
        <span role="status" className="text-muted">Loading review…</span>
      </Empty>
    );
  }

  const review = data;

  const executionState = review.workflow_status || review.status;
  const publicationState =
    review.publication_status || (review.github_review_id ? "posted" : "unposted");

  async function copyMarkdown() {
    const findingsText = review.findings
      .map(
        (f) =>
          `### [${(f.severity || "UNKNOWN").toUpperCase()}] ${f.summary}\n` +
          `File: ${f.file_path || "General"}${f.line_start ? `:${f.line_start}` : ""}\n` +
          `Specialist: ${f.agent_type || "agent"}\n` +
          (f.suggestion ? `Suggested change:\n\`\`\`\n${f.suggestion}\n\`\`\`\n` : "")
      )
      .join("\n");

    const markdown = [
      `# Review: ${review.repo_full_name} #${review.pr_number}`,
      `Title: ${review.pr_title || "Untitled PR"}`,
      `Commit: ${review.head_commit_sha}`,
      `Execution status: ${executionState}`,
      `Publication status: ${publicationState}`,
      `Recommendation: ${review.verdict || "Not available"}`,
      `Confidence: ${
        review.overall_confidence != null
          ? `${Math.round(review.overall_confidence * 100)}%`
          : "Not available"
      }`,
      `Date: ${new Date(review.created_at).toUTCString()}`,
      "",
      "## Findings",
      findingsText || "No findings recorded.",
      "",
      "> Note: Automated findings do not imply all code was examined. Human assessment is required.",
    ].join("\n");

    try {
      await navigator.clipboard.writeText(markdown);
      setCopyStatus("Review copied to clipboard as Markdown.");
    } catch {
      setCopyStatus("Clipboard write was unavailable. Please copy details manually.");
    }
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <Link href="/reviews" className="hover:text-foreground underline-offset-4 hover:underline">
          Reviews
        </Link>
        <span aria-hidden="true">/</span>
        <span className="font-mono">{review.repo_full_name}</span>
        <span aria-hidden="true">/</span>
        <span aria-current="page" className="font-semibold text-foreground">
          #{review.pr_number}
        </span>
      </nav>

      {/* Detail Header */}
      <header className="space-y-4 rounded-xl border border-border bg-panel p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2 font-mono text-xs text-muted">
              <span className="font-medium text-foreground">{review.repo_full_name}</span>
              <span>#{review.pr_number}</span>
              <span>•</span>
              <span title="Head commit SHA">{review.head_commit_sha.slice(0, 8)}</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground break-words">
              {review.pr_title || `Pull request #${review.pr_number}`}
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <ReviewStatusBadge status={review.status} />
            <VerdictChip verdict={review.verdict} />
          </div>
        </div>

        {/* Status Indicators & Metadata */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border text-xs">
          <div className="flex flex-wrap items-center gap-4 text-muted">
            <span>
              Execution: <strong className="text-foreground font-mono">{executionState}</strong>
            </span>
            <span>
              Publication:{" "}
              <strong className="text-foreground font-mono">{publicationState}</strong>
            </span>
            {review.human_decision && (
              <span>
                Human determination:{" "}
                <strong className="text-foreground font-mono">{review.human_decision}</strong>
              </span>
            )}
            <time dateTime={review.created_at}>
              Created {new Date(review.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </time>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <a
              href={`https://github.com/${review.repo_full_name}/pull/${review.pr_number}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex min-h-9 items-center rounded-lg border border-border bg-surface px-3 text-xs font-medium text-foreground hover:bg-raised transition-colors"
            >
              GitHub PR <span aria-hidden="true" className="ml-1">↗</span>
            </a>
            <Button variant="outline" size="sm" onClick={() => void copyMarkdown()}>
              Copy as Markdown
            </Button>
          </div>
        </div>

        {copyStatus && (
          <p role="status" className="text-xs text-accent transition-opacity">
            {copyStatus}
          </p>
        )}
      </header>

      {/* Executive Summary */}
      <ExecutiveReviewSummary data={review} />

      {/* View Switcher Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div role="tablist" aria-label="Review content views" className="flex gap-2">
          <button
            role="tab"
            aria-selected={activeView === "findings"}
            onClick={() => setActiveView("findings")}
            className={`min-h-9 rounded-lg px-3.5 text-xs font-medium transition-colors ${
              activeView === "findings"
                ? "bg-primary-action text-foreground font-semibold"
                : "text-muted hover:text-foreground hover:bg-surface border border-border"
            }`}
          >
            Findings ({review.findings.length})
          </button>
          <button
            role="tab"
            aria-selected={activeView === "diff"}
            onClick={() => setActiveView("diff")}
            className={`min-h-9 rounded-lg px-3.5 text-xs font-medium transition-colors ${
              activeView === "diff"
                ? "bg-primary-action text-foreground font-semibold"
                : "text-muted hover:text-foreground hover:bg-surface border border-border"
            }`}
          >
            Unified Diff
          </button>
        </div>

        <div className="text-xs text-muted">
          <span>
            Model confidence:{" "}
            <strong className="text-foreground">
              {review.overall_confidence != null && Number.isFinite(review.overall_confidence)
                ? `${Math.round(review.overall_confidence * 100)}%`
                : "Not available"}
            </strong>
          </span>
        </div>
      </div>

      {/* Active Tab View */}
      {activeView === "findings" ? (
        <FindingsByAgent findings={review.findings ?? []} />
      ) : (
        <DiffViewer diff={review.pr_diff || undefined} findings={review.findings ?? []} />
      )}

      {/* Technical Details Accordion */}
      <details className="rounded-xl border border-border bg-panel">
        <summary className="cursor-pointer px-5 py-4 text-xs font-medium text-muted hover:text-foreground transition-colors">
          Technical Review Provenance & Metadata
        </summary>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 border-t border-border p-5 text-xs">
          <div>
            <dt className="text-muted">Head commit SHA</dt>
            <dd className="mt-1 break-all font-mono text-foreground">{review.head_commit_sha}</dd>
          </div>
          <div>
            <dt className="text-muted">Review record ID</dt>
            <dd className="mt-1 break-all font-mono text-foreground">{review.id}</dd>
          </div>
          <div>
            <dt className="text-muted">Last updated</dt>
            <dd className="mt-1 text-foreground">{new Date(review.updated_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-muted">GitHub Review ID</dt>
            <dd className="mt-1 font-mono text-foreground">
              {review.github_review_id ?? "Not posted to GitHub"}
            </dd>
          </div>
        </dl>
      </details>
    </div>
  );
}
