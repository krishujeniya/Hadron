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
        status: "Awaiting PR reviews",
        statusTone: "text-muted",
        pillars: [
          { name: "Evaluated pull requests", score: "0", desc: "No reviews run in this window" },
          { name: "Escalation queue", score: `${pendingHitlCount}`, desc: "Pending human decisions" },
          { name: "Monitored repositories", score: `${watchedReposCount}`, desc: "Configured repositories" },
          { name: "Approval rate", score: "—", desc: "Requires completed reviews" },
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
        ? `${pendingHitlCount} PR(s) escalated to human review`
        : changesRequested > 0
        ? `${changesRequested} PR(s) changes requested`
        : "All reviewed PRs approved";

    return {
      scoreDisplay: `${approvalRate}%`,
      scoreNumber: approvalRate,
      status: statusText,
      statusTone: pendingHitlCount > 0 ? "text-warn" : "text-ok",
      pillars: [
        { name: "Evaluated pull requests", score: `${reviews.length}`, desc: "Total pull requests reviewed" },
        { name: "Approval rate", score: `${approvalRate}%`, desc: "Automated passes approved" },
        { name: "Escalation queue", score: `${pendingHitlCount}`, desc: "Awaiting human review" },
        { name: "Monitored repositories", score: `${watchedReposCount}`, desc: "Configured repositories" },
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
    <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm relative overflow-hidden">
      <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 pb-6 border-b border-separator">
        {/* Left: Score Gauge */}
        <div className="flex items-center gap-5">
          <div className="relative flex items-center justify-center w-28 h-28 shrink-0">
            <svg className="w-full h-full -rotate-90 transform" viewBox="0 0 100 100" aria-hidden="true">
              {/* Background ring */}
              <circle
                cx="50"
                cy="50"
                r={radius}
                className="stroke-border/40"
                strokeWidth="8"
                fill="transparent"
              />
              {/* Foreground ring */}
              {scoreNumber > 0 && (
                <circle
                  cx="50"
                  cy="50"
                  r={radius}
                  stroke="rgb(var(--accent))"
                  strokeWidth="8"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                  fill="transparent"
                  className="transition-all duration-1000 ease-out"
                />
              )}
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <span className="text-2xl font-extrabold tracking-tighter text-foreground font-mono">
                {scoreDisplay}
              </span>
              <span className="text-[10px] font-mono uppercase tracking-widest text-muted -mt-1">
                Pass rate
              </span>
            </div>
          </div>

          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold bg-panel border border-border text-foreground shadow-xs">
              <span className={`w-2 h-2 rounded-full ${scoreNumber > 0 ? "bg-ok animate-pulse" : "bg-muted"}`} />
              <span className={statusTone}>{status}</span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-foreground mt-2 font-mono">
              PR review health &amp; escalation telemetry
            </h2>
            <p className="text-xs text-muted mt-1 max-w-lg leading-relaxed">
              Measured operational metrics from automated specialist agents and human-in-the-loop dispute workflows.
            </p>
          </div>
        </div>

        {/* Right: Operational Counts */}
        <div className="grid grid-cols-3 gap-3 w-full lg:w-auto shrink-0">
          <div className="p-3 rounded-xl border border-border bg-panel text-center">
            <div className="text-[10px] uppercase font-mono tracking-wider text-muted">Total PRs</div>
            <div className="text-lg font-bold text-foreground mt-0.5">{metrics.totalReviews}</div>
            <div className="text-[10px] text-muted">Evaluated</div>
          </div>
          <div className="p-3 rounded-xl border border-border bg-panel text-center">
            <div className="text-[10px] uppercase font-mono tracking-wider text-muted">Approved</div>
            <div className="text-lg font-bold text-ok mt-0.5">{metrics.approvedCount}</div>
            <div className="text-[10px] text-muted">Passed review</div>
          </div>
          <div className="p-3 rounded-xl border border-border bg-panel text-center">
            <div className="text-[10px] uppercase font-mono tracking-wider text-muted">Escalated</div>
            <div className="text-lg font-bold text-warn mt-0.5">{metrics.pendingHitlCount}</div>
            <div className="text-[10px] text-muted">Pending human</div>
          </div>
        </div>
      </div>

      {/* Core Operational Pillars */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
        {pillars.map((pillar) => (
          <div
            key={pillar.name}
            className="p-3.5 rounded-xl border border-border bg-panel hover:bg-surface transition-all"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-foreground">{pillar.name}</span>
              <span className="text-xs font-mono font-bold text-foreground bg-surface px-1.5 py-0.5 rounded border border-border">
                {pillar.score}
              </span>
            </div>
            <p className="text-[11px] text-muted mt-1.5 leading-snug">{pillar.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
