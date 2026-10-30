"use client";

import { useMemo } from "react";
import type { ReviewSummary } from "@/lib/types";

interface ExecutiveHealthScoreProps {
  reviews: ReviewSummary[];
  watchedReposCount: number;
  pendingHitlCount: number;
}

export function ExecutiveHealthScore({
  reviews,
  watchedReposCount,
  pendingHitlCount,
}: ExecutiveHealthScoreProps) {
  // Compute honest operational telemetry based on actual reviews
  const { scoreDisplay, scoreNumber, status, statusTone, pillars, metrics } = useMemo(() => {
    if (reviews.length === 0) {
      return {
        scoreDisplay: "—",
        scoreNumber: 0,
        status: "Awaiting PR Reviews",
        statusTone: "text-zinc-400",
        pillars: [
          { name: "Evaluated PRs", score: "0", desc: "No reviews run in this window" },
          { name: "Escalation Queue", score: `${pendingHitlCount}`, desc: "Pending human decisions" },
          { name: "Monitored Repos", score: `${watchedReposCount}`, desc: "Configured repositories" },
          { name: "Approval Rate", score: "—", desc: "Requires completed reviews" },
        ],
        metrics: {
          totalReviews: 0,
          approvedCount: 0,
          changesRequestedCount: 0,
          pendingHitlCount,
        },
      };
    }

    const approved = reviews.filter((r) => r.verdict === "approve").length;
    const changesRequested = reviews.filter((r) => r.verdict === "request_changes").length;
    const approvalRate = Math.round((approved / reviews.length) * 100);

    const statusText =
      pendingHitlCount > 0
        ? `${pendingHitlCount} PR(s) Escalated to Human Review`
        : changesRequested > 0
        ? `${changesRequested} PR(s) Changes Requested`
        : "All Reviewed PRs Approved";

    return {
      scoreDisplay: `${approvalRate}%`,
      scoreNumber: approvalRate,
      status: statusText,
      statusTone: pendingHitlCount > 0 ? "text-amber-400" : "text-white",
      pillars: [
        { name: "Evaluated PRs", score: `${reviews.length}`, desc: "Total pull requests reviewed" },
        { name: "Approval Rate", score: `${approvalRate}%`, desc: "Automated passes approved" },
        { name: "Escalation Queue", score: `${pendingHitlCount}`, desc: "Awaiting human review" },
        { name: "Monitored Repos", score: `${watchedReposCount}`, desc: "Configured repositories" },
      ],
      metrics: {
        totalReviews: reviews.length,
        approvedCount: approved,
        changesRequestedCount: changesRequested,
        pendingHitlCount,
      },
    };
  }, [reviews, pendingHitlCount, watchedReposCount]);

  // Circumference for 44px radius circle (2 * PI * 44 ≈ 276.46)
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (scoreNumber / 100) * circumference;

  return (
    <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-zinc-900/90 via-zinc-950/95 to-black p-6 shadow-2xl relative overflow-hidden">
      {/* Subtle ambient light effect */}
      <div className="absolute top-0 right-1/4 w-96 h-48 bg-white/[0.03] rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 pb-6 border-b border-white/10">
        {/* Left: Score Gauge */}
        <div className="flex items-center gap-5">
          <div className="relative flex items-center justify-center w-28 h-28 shrink-0">
            <svg className="w-full h-full -rotate-90 transform" viewBox="0 0 100 100">
              {/* Background ring */}
              <circle
                cx="50"
                cy="50"
                r={radius}
                className="stroke-zinc-800"
                strokeWidth="8"
                fill="transparent"
              />
              {/* Foreground gradient animated ring */}
              {scoreNumber > 0 && (
                <circle
                  cx="50"
                  cy="50"
                  r={radius}
                  stroke="url(#scoreGrad)"
                  strokeWidth="8"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                  fill="transparent"
                  className="transition-all duration-1000 ease-out"
                />
              )}
              <defs>
                <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#FFFFFF" />
                  <stop offset="50%" stopColor="#D4D4D8" />
                  <stop offset="100%" stopColor="#71717A" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <span className="text-2xl font-extrabold tracking-tighter bg-gradient-to-b from-white via-zinc-100 to-zinc-400 bg-clip-text text-transparent">
                {scoreDisplay}
              </span>
              <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-400 -mt-1">
                Pass Rate
              </span>
            </div>
          </div>

          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold bg-white/10 border border-white/20 text-white shadow-xs">
              <span className={`w-2 h-2 rounded-full ${scoreNumber > 0 ? "bg-white animate-pulse" : "bg-zinc-500"}`} />
              <span className={statusTone}>{status}</span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-white mt-2">
              PR Review Health & Escalation Telemetry
            </h2>
            <p className="text-xs text-zinc-400 mt-1 max-w-lg leading-relaxed">
              Measured operational metrics from automated specialist agents and human-in-the-loop dispute workflows.
            </p>
          </div>
        </div>

        {/* Right: Operational Counts */}
        <div className="grid grid-cols-3 gap-3 w-full lg:w-auto shrink-0">
          <div className="p-3 rounded-xl border border-white/10 bg-black/60 text-center">
            <div className="text-[10px] uppercase font-mono tracking-wider text-zinc-400">Total PRs</div>
            <div className="text-lg font-bold text-white mt-0.5">{metrics.totalReviews}</div>
            <div className="text-[10px] text-zinc-500">Evaluated</div>
          </div>
          <div className="p-3 rounded-xl border border-white/10 bg-black/60 text-center">
            <div className="text-[10px] uppercase font-mono tracking-wider text-zinc-400">Approved</div>
            <div className="text-lg font-bold text-white mt-0.5">{metrics.approvedCount}</div>
            <div className="text-[10px] text-zinc-500">Passed review</div>
          </div>
          <div className="p-3 rounded-xl border border-white/10 bg-black/60 text-center">
            <div className="text-[10px] uppercase font-mono tracking-wider text-zinc-400">Escalated</div>
            <div className="text-lg font-bold text-white mt-0.5">{metrics.pendingHitlCount}</div>
            <div className="text-[10px] text-zinc-500">Pending human</div>
          </div>
        </div>
      </div>

      {/* Core Operational Pillars */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
        {pillars.map((pillar) => (
          <div
            key={pillar.name}
            className="p-3.5 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] transition-all"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-200">{pillar.name}</span>
              <span className="text-xs font-mono font-bold text-white bg-white/10 px-1.5 py-0.5 rounded border border-white/10">
                {pillar.score}
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 mt-1.5 leading-snug">{pillar.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
