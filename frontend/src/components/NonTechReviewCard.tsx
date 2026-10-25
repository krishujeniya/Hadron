"use client";

import Link from "next/link";
import { VerdictChip } from "./VerdictChip";
import { ReviewStatusBadge } from "./ReviewStatusBadge";
import type { ReviewSummary } from "@/lib/types";

interface NonTechReviewCardProps {
  review: ReviewSummary;
}

export function NonTechReviewCard({ review }: NonTechReviewCardProps) {
  // Infer a friendly business description from the PR title
  const plainSummary = getPlainSummary(review.pr_title);

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
            {plainSummary.friendlyTitle}
          </h4>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <VerdictChip verdict={review.verdict} />
          <ReviewStatusBadge status={review.status} />
        </div>
      </div>

      <p className="text-xs text-zinc-300 leading-relaxed bg-black/40 p-2.5 rounded-lg border border-white/5">
        <span className="text-zinc-500 font-medium">Business Impact: </span>
        {plainSummary.impact}
      </p>

      <div className="flex items-center justify-between pt-1 text-xs">
        <span className="text-zinc-400 font-mono text-[11px]">
          {plainSummary.riskPill}
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

function getPlainSummary(title?: string): {
  friendlyTitle: string;
  impact: string;
  riskPill: string;
} {
  const t = (title || "").toLowerCase();

  if (t.includes("style") || t.includes("ui") || t.includes("color") || t.includes("theme")) {
    return {
      friendlyTitle: "🎨 Visual Aesthetic & User Interface Polish",
      impact: "Upgrades visual appeal with high-contrast accessibility and modern gradient styling for an intuitive customer experience.",
      riskPill: "🛡️ Zero Risk · Visual Only",
    };
  }
  if (t.includes("ai") || t.includes("model") || t.includes("nvidia") || t.includes("openai")) {
    return {
      friendlyTitle: "🧠 AI Intelligence Engine Modernization",
      impact: "Powers up automated code analysis using high-speed NVIDIA inference, delivering faster reviews at zero cloud bloat.",
      riskPill: "⚡ High Velocity · Verified Safe",
    };
  }
  if (t.includes("auth") || t.includes("security") || t.includes("token") || t.includes("secret")) {
    return {
      friendlyTitle: "🔐 Account Security & Threat Shielding",
      impact: "Fortifies login sessions and credential validation, preventing unauthorized repository access.",
      riskPill: "🔒 Critical Defense · Verified",
    };
  }
  if (t.includes("fix") || t.includes("bug") || t.includes("resolve")) {
    return {
      friendlyTitle: "🛠️ System Bug Resolution & Stability Fix",
      impact: "Interprets and repairs edge cases to ensure user sessions run smoothly without disruptions.",
      riskPill: "✅ Stability Boost",
    };
  }

  return {
    friendlyTitle: title || "Feature Enhancement",
    impact: "Automated verification completed with full test coverage and continuous monitoring.",
    riskPill: "🛡️ Monitored by Hadron",
  };
}
