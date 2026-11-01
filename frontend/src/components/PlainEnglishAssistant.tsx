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
    <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm space-y-5">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-separator pb-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-panel text-muted border border-border">
            <span>📊</span> Operational Guidance
          </div>
          <h3 className="text-lg font-bold text-foreground mt-1.5 font-mono">
            Workspace PR Review Summary
          </h3>
          <p className="text-xs text-muted">
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
              ? "bg-accent/15 text-accent border-accent/40 font-semibold shadow-xs"
              : "bg-panel text-muted border-border hover:border-muted/50 hover:text-foreground"
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
              ? "bg-accent/15 text-accent border-accent/40 font-semibold shadow-xs"
              : "bg-panel text-muted border-border hover:border-muted/50 hover:text-foreground"
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
              ? "bg-accent/15 text-accent border-accent/40 font-semibold shadow-xs"
              : "bg-panel text-muted border-border hover:border-muted/50 hover:text-foreground"
          }`}
        >
          <span>⚡ Approvals Queue ({hitlCount})</span>
        </button>
      </div>

      {/* Content Area */}
      <div className="p-4 rounded-xl border border-border bg-panel text-xs text-foreground/90 leading-relaxed min-h-[90px] flex items-center">
        {customResponse ? (
          <div>
            <div className="font-semibold text-accent mb-1 font-mono uppercase tracking-wider text-[10px]">
              Query Result:
            </div>
            <p>{customResponse}</p>
          </div>
        ) : activeTab === "summary" ? (
          <div>
            <span className="font-semibold text-foreground">Activity Summary: </span>
            {totalCount === 0
              ? `No reviews run yet in this workspace. Pull requests opened on watched repositories will show automated findings here.`
              : `${totalCount} pull request reviews recorded in this window. ${approvedCount} approved without blocking findings, ${changesCount} have requested changes, and ${hitlCount} require human review.`}
          </div>
        ) : activeTab === "security" ? (
          <div>
            <span className="font-semibold text-foreground">Security Posture: </span>
            {totalCount === 0
              ? `Awaiting pull requests to run automated security analysis.`
              : `Security agent scans diffs for hardcoded credentials, injection vulnerabilities, and dangerous dependency changes.`}
          </div>
        ) : (
          <div>
            <span className="font-semibold text-foreground">Human Approvals: </span>
            {hitlCount === 0
              ? `No reviews currently require human-in-the-loop sign-off. The queue is clear.`
              : `${hitlCount} review(s) are awaiting human evaluation due to low agent confidence or critical severity thresholds.`}
          </div>
        )}
      </div>

      {/* Interactive Query Input */}
      <form onSubmit={handleCustomSubmit} className="flex gap-2">
        <input
          type="text"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          placeholder="Ask an operational question (e.g. 'Are any security issues blocking release?')..."
          className="flex-1 bg-panel border border-border rounded-xl px-3.5 py-2 text-xs text-foreground placeholder:text-muted/60 focus:outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={isThinking || !customInput.trim()}
          className="px-4 py-2 bg-primary-action text-white hover:bg-primary-action/90 font-medium text-xs rounded-xl transition disabled:opacity-50 shrink-0 shadow-sm"
        >
          {isThinking ? "Analyzing..." : "Ask Assistant"}
        </button>
      </form>
    </div>
  );
}
