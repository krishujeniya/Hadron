"use client";

import { useState } from "react";
import type { ReviewSummary } from "@/lib/types";

interface PlainEnglishAssistantProps {
  recentReviews: ReviewSummary[];
  accountName?: string;
}

export function PlainEnglishAssistant({ recentReviews, accountName }: PlainEnglishAssistantProps) {
  const [activeTab, setActiveTab] = useState<"summary" | "security" | "escalations">("summary");
  const [customInput, setCustomInput] = useState("");
  const [customResponse, setCustomResponse] = useState<string | null>(null);
  const [isThinking, setIsThinking] = useState(false);

  const totalCount = recentReviews.length;
  const approvedCount = recentReviews.filter((r) => r.verdict === "approve").length;
  const changesCount = recentReviews.filter((r) => r.verdict === "request_changes").length;
  const hitlCount = recentReviews.filter((r) => r.verdict === "needs_human_review").length;

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customInput.trim()) return;

    setIsThinking(true);
    setCustomResponse(null);

    setTimeout(() => {
      const query = customInput.toLowerCase();
      let reply: string;

      if (totalCount === 0) {
        reply = `No review records are loaded for ${accountName ? `@${accountName}` : "this workspace"}. Submit or sync pull requests to inspect review results.`;
      } else if (query.includes("slow") || query.includes("performance") || query.includes("speed")) {
        reply = `Among the ${totalCount} evaluated PR(s), automated passes measure code quality and test coverage. Specific runtime performance benchmarks require repository CI job results.`;
      } else if (query.includes("cost") || query.includes("budget") || query.includes("bill")) {
        reply = `AI review token spend is constrained by daily budget quotas. Detailed per-PR cost attribution is tracked in the Operations Cost Ledger.`;
      } else if (query.includes("security") || query.includes("secret") || query.includes("safe")) {
        reply = `Security analysis across the ${totalCount} recorded PR(s) evaluated secret detection, dependency risks, and injection patterns. ${hitlCount} PR(s) are escalated for human verification.`;
      } else {
        reply = `Workspace Status: ${totalCount} PR(s) evaluated in this view (${approvedCount} approved, ${changesCount} changes requested, ${hitlCount} awaiting human decision).`;
      }

      setCustomResponse(reply);
      setIsThinking(false);
    }, 200);
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-zinc-950 via-zinc-900 to-black p-6 shadow-xl space-y-5">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-white/10 pb-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-white/10 text-white border border-white/20">
            <span>📊</span> Operational Guidance
          </div>
          <h3 className="text-lg font-bold text-white mt-1.5">
            Workspace PR Review Summary
          </h3>
          <p className="text-xs text-zinc-400">
            Factual overview derived from recent review results in {accountName ? `@${accountName}` : "your workspace"}.
          </p>
        </div>
      </div>

      {/* Preset Tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            setActiveTab("summary");
            setCustomResponse(null);
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all text-left flex items-center gap-2 border ${
            activeTab === "summary" && !customResponse
              ? "bg-white text-black border-white font-semibold shadow-md shadow-white/10"
              : "bg-white/[0.03] text-zinc-300 border-white/10 hover:border-white/30 hover:bg-white/[0.06]"
          }`}
        >
          <span>📋 Overview</span>
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab("security");
            setCustomResponse(null);
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all text-left flex items-center gap-2 border ${
            activeTab === "security" && !customResponse
              ? "bg-white text-black border-white font-semibold shadow-md shadow-white/10"
              : "bg-white/[0.03] text-zinc-300 border-white/10 hover:border-white/30 hover:bg-white/[0.06]"
          }`}
        >
          <span>🛡️ Security Status</span>
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab("escalations");
            setCustomResponse(null);
          }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all text-left flex items-center gap-2 border ${
            activeTab === "escalations" && !customResponse
              ? "bg-white text-black border-white font-semibold shadow-md shadow-white/10"
              : "bg-white/[0.03] text-zinc-300 border-white/10 hover:border-white/30 hover:bg-white/[0.06]"
          }`}
        >
          <span>⚠️ Escalation Queue</span>
        </button>
      </div>

      {/* Guidance Answer Card */}
      <div className="rounded-xl border border-white/10 bg-black/80 p-4 space-y-2 relative overflow-hidden">
        <div className="flex items-center justify-between text-xs font-mono text-zinc-400 border-b border-white/10 pb-2">
          <span className="font-semibold text-white">
            {customResponse
              ? "Workspace Query Result"
              : activeTab === "summary"
              ? "PR Review Overview"
              : activeTab === "security"
              ? "Security Screening Status"
              : "Human-in-the-Loop Escalations"}
          </span>
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
            Measured Data
          </span>
        </div>

        {isThinking ? (
          <div className="py-4 flex items-center justify-center gap-2 text-xs text-zinc-400 font-mono">
            <span className="w-2 h-2 rounded-full bg-white animate-ping" />
            Filtering workspace telemetry...
          </div>
        ) : customResponse ? (
          <p className="text-sm text-zinc-200 leading-relaxed pt-1">{customResponse}</p>
        ) : totalCount === 0 ? (
          <p className="text-sm text-zinc-400 leading-relaxed pt-1">
            No pull request reviews have been executed yet in this workspace. Trigger an automated review or submit a PR to inspect findings.
          </p>
        ) : activeTab === "summary" ? (
          <div className="text-sm text-zinc-200 leading-relaxed pt-1 space-y-2">
            <p>
              Across {totalCount} reviewed pull request(s): {approvedCount} approved, {changesCount} requested changes, and {hitlCount} required human intervention.
            </p>
            <p className="text-xs text-zinc-400">
              Note: Automated multi-agent passes provide assistive screening and do not guarantee the absence of all defects. Final merge authorization remains with human maintainers.
            </p>
          </div>
        ) : activeTab === "security" ? (
          <div className="text-sm text-zinc-200 leading-relaxed pt-1 space-y-2">
            <p>
              Security specialist agents evaluate credentials, dependency alerts, and diff integrity on every PR.
            </p>
            <p className="text-xs text-zinc-400">
              {changesCount + hitlCount > 0
                ? `${changesCount + hitlCount} PR(s) currently require maintainer review due to security or critical findings.`
                : "No blocking security vulnerabilities are currently flagged on active approved PRs."}
            </p>
          </div>
        ) : (
          <div className="text-sm text-zinc-200 leading-relaxed pt-1 space-y-2">
            <p>
              {hitlCount > 0
                ? `${hitlCount} pull request(s) are held in the Human-in-the-Loop queue for maintainer decision.`
                : "Zero PRs currently require human dispute escalation."}
            </p>
            <p className="text-xs text-zinc-400">
              Reviews escalate to HITL when confidence is below threshold, security checks fail, or agents disagree on critical findings.
            </p>
          </div>
        )}
      </div>

      {/* Query Filter Input */}
      <form onSubmit={handleCustomSubmit} className="flex items-center gap-2">
        <label htmlFor="workspace-query-input" className="sr-only">
          Ask a question about current review status
        </label>
        <input
          id="workspace-query-input"
          type="text"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          placeholder="Query workspace reviews: e.g. 'Are any PRs waiting for human review?'"
          className="flex-1 bg-black/60 border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/40 transition-colors"
        />
        <button
          type="submit"
          disabled={!customInput.trim() || isThinking}
          className="px-4 py-2 rounded-xl bg-gradient-to-b from-white to-zinc-200 text-black text-xs font-semibold hover:from-zinc-100 hover:to-zinc-300 transition-all shadow-xs disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          Check
        </button>
      </form>
    </div>
  );
}
