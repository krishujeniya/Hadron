"use client";

import Link from "next/link";
import { VerdictChip } from "./VerdictChip";
import { ReviewStatusBadge } from "./ReviewStatusBadge";
import type { ReviewSummary } from "@/lib/types";

interface NonTechReviewCardProps {
  review: ReviewSummary;
}

export function NonTechReviewCard({ review }: NonTechReviewCardProps) {
  const summary = getReviewOperationalSummary(review);

  return (
    <div className="rounded-xl border border-white/10 bg-gradient-to-b from-zinc-900/40 to-black/80 p-4 hover:border-white/20 transition-all shadow-xs space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 bg-white/5 px-2 py-0.5 rounded border border-white/10">
              PR #{review.pr_number}
            </span>
            <span className="text-xs font-mono text-zinc-400 truncate">
              {review.repo_full_name}
            </span>
          </div>
          <h4 className="text-sm font-semibold text-white mt-1 truncate">
            {review.pr_title || "Untitled Pull Request"}
          </h4>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <VerdictChip verdict={review.verdict} />
          <ReviewStatusBadge status={review.status} />
        </div>
      </div>

      <p className="text-xs text-zinc-300 leading-relaxed bg-black/40 p-2.5 rounded-lg border border-white/5">
        <span className="text-zinc-500 font-medium">Review Status: </span>
        {summary.impact}
      </p>

      <div className="flex items-center justify-between pt-1 text-xs">
        <span className="text-zinc-400 font-mono text-[11px]">
          {summary.riskPill}
        </span>
        <Link
          href={`/reviews/${encodeURIComponent(review.id)}`}
          className="inline-flex items-center gap-1 font-semibold text-white hover:text-zinc-300 transition-colors"
        >
          Inspect Details →
        </Link>
      </div>
    </div>
  );
}

function getReviewOperationalSummary(review: ReviewSummary): {
  impact: string;
  riskPill: string;
} {
  if (review.verdict === "approve") {
    return {
      impact: "Automated multi-agent screening passed without blocking issues.",
      riskPill: "Automated Pass",
    };
  }

  if (review.verdict === "request_changes") {
    return {
      impact: "Specialist agents identified code issues requiring developer attention before merge.",
      riskPill: "Changes Requested",
    };
  }

  if (review.verdict === "needs_human_review") {
    return {
      impact: "Review confidence or safety criteria triggered human-in-the-loop escalation.",
      riskPill: "Pending Human Review",
    };
  }

  return {
    impact: "Review is currently being processed by automated agent pipeline.",
    riskPill: "In Progress",
  };
}
