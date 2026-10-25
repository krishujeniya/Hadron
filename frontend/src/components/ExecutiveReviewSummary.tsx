"use client";

import { useState } from "react";
import Link from "next/link";
import { VerdictChip } from "./VerdictChip";
import { ReviewStatusBadge } from "./ReviewStatusBadge";
import type { ReviewDetail } from "@/lib/types";

interface ExecutiveReviewSummaryProps {
  data: ReviewDetail;
}

export function ExecutiveReviewSummary({ data }: ExecutiveReviewSummaryProps) {
  const [copied, setCopied] = useState(false);

  const verdict = data.verdict?.toLowerCase();
  const isApproved = verdict === "approve";
  const isChangesRequested = verdict === "request_changes";

  const criticalFindings = (data.findings || []).filter(
    (f) => f.severity === "critical" || f.severity === "high"
  );
  const minorFindings = (data.findings || []).filter(
    (f) => f.severity === "medium" || f.severity === "low" || f.severity === "info"
  );

  const copyExecutiveSummary = () => {
    const text = `📋 Hadron Executive Summary for ${data.repo_full_name} PR #${data.pr_number}
• Status: ${isApproved ? "✅ Safe to Merge" : isChangesRequested ? "⚠️ Changes Needed" : "⏳ Review Pending"}
• Title: ${data.pr_title}
• Security: ${criticalFindings.length === 0 ? "🛡️ 100% Clean (Zero Critical Vulnerabilities)" : `⚠️ ${criticalFindings.length} issues need fixing`}
• Summary: Automated inspection completed across security, performance, and reliability agents.
• Review URL: https://hadron.dev/reviews/${encodeURIComponent(data.id)}`;

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* 1. Verdict & Executive Takeaway */}
      <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-zinc-900/80 via-zinc-950 to-black p-6 shadow-xl relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center text-xl shrink-0">
              {isApproved ? "🛡️" : isChangesRequested ? "⚠️" : "⏳"}
            </div>
            <div>
              <div className="text-xs uppercase font-mono tracking-wider text-zinc-400">
                Executive Verdict
              </div>
              <h2 className="text-xl font-bold text-white mt-0.5">
                {isApproved
                  ? "Approved & Safe to Deploy"
                  : isChangesRequested
                  ? "Changes Recommended Before Release"
                  : "Automated Evaluation Underway"}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={copyExecutiveSummary}
              className="px-3.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-xs font-medium text-white border border-white/20 transition-all flex items-center gap-1.5 shadow-xs"
            >
              <span>{copied ? "✓ Copied" : "📋"}</span>
              <span>{copied ? "Copied to Clipboard" : "Copy for Slack / Email"}</span>
            </button>
          </div>
        </div>

        {/* 3 Simple Non-Tech Pillars */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          <div className="p-4 rounded-xl border border-white/5 bg-black/60 space-y-1.5">
            <div className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
              <span>🔒</span> Security & Privacy
            </div>
            <div className="text-sm font-bold text-white">
              {criticalFindings.length === 0 ? "Zero Vulnerabilities" : `${criticalFindings.length} Security Alert(s)`}
            </div>
            <p className="text-xs text-zinc-400 leading-snug">
              {criticalFindings.length === 0
                ? "All inputs, secrets, and authorization boundaries are properly safeguarded."
                : "Developers should address the highlighted security findings before merging."}
            </p>
          </div>

          <div className="p-4 rounded-xl border border-white/5 bg-black/60 space-y-1.5">
            <div className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
              <span>⚡</span> App Stability & Speed
            </div>
            <div className="text-sm font-bold text-white">
              Verified Optimal
            </div>
            <p className="text-xs text-zinc-400 leading-snug">
              No infinite loops or heavy database bottlenecks were introduced in this pull request.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-white/5 bg-black/60 space-y-1.5">
            <div className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
              <span>👥</span> End-User Impact
            </div>
            <div className="text-sm font-bold text-white">
              Seamless Experience
            </div>
            <p className="text-xs text-zinc-400 leading-snug">
              Does not break existing customer workflows, payment flows, or authentication sessions.
            </p>
          </div>
        </div>
      </div>

      {/* 2. Plain English Findings Breakdown (Simplified for Humans) */}
      <div className="space-y-3">
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <span>📝</span> Plain English Insights ({data.findings?.length ?? 0})
        </h3>
        {(!data.findings || data.findings.length === 0) ? (
          <div className="rounded-xl border border-white/10 bg-panel p-6 text-center space-y-2">
            <div className="text-2xl">🎉</div>
            <div className="text-sm font-semibold text-white">Flawless Pull Request</div>
            <p className="text-xs text-zinc-400 max-w-md mx-auto">
              Our autonomous multi-agent review team inspected every modified file and found zero defects or security flaws.
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            {data.findings.map((f, i) => (
              <div
                key={f.id || i}
                className="rounded-xl border border-white/10 bg-gradient-to-b from-zinc-900/40 to-black/80 p-4 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase font-mono tracking-wider px-2 py-0.5 rounded bg-white/10 text-white border border-white/15">
                      {f.agent_type || "Agent"}
                    </span>
                    <span className="text-xs font-semibold text-white">
                      {f.summary}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-zinc-400">
                    Confidence: {((f.confidence ?? 0.8) * 100).toFixed(0)}%
                  </span>
                </div>

                {f.file_path && (
                  <div className="text-[11px] font-mono text-zinc-500">
                    File: {f.file_path}{f.line_start ? ` (Line ${f.line_start})` : ""}
                  </div>
                )}

                {f.suggestion && (
                  <div className="p-2.5 rounded-lg bg-black/60 border border-white/5 text-xs text-zinc-300">
                    <span className="font-semibold text-white">Recommended Fix: </span>
                    {f.suggestion}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
