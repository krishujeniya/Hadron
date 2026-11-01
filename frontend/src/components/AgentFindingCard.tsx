"use client";

import { useState } from "react";
import { SeverityChip } from "./SeverityChip";
import type { Finding } from "@/lib/types";

const AGENTS: Record<string, string> = {
  security: "Security Specialist",
  quality: "Code Quality Specialist",
  test_coverage: "Test Coverage Specialist",
  documentation: "Documentation Specialist",
};

export function FindingCard({ finding, index }: { finding: Finding; index?: number }) {
  const confidence =
    finding.confidence != null && Number.isFinite(finding.confidence)
      ? `${Math.round(finding.confidence * 100)}%`
      : "Not available";

  const anchorId = finding.id ? `finding-${finding.id}` : `finding-${index ?? 0}`;

  return (
    <article
      id={anchorId}
      className="px-4 py-5 sm:px-5 space-y-3 scroll-mt-24 transition-colors hover:bg-surface/30"
    >
      <div className="flex flex-wrap items-center gap-2">
        <SeverityChip severity={finding.severity} />
        <span className="text-xs font-medium text-accent">
          {AGENTS[finding.agent_type] ?? finding.agent_type.replaceAll("_", " ")}
        </span>
        <span className="text-xs text-muted font-mono">
          Model confidence: {confidence}
        </span>
      </div>

      <h3 className="text-sm font-medium leading-relaxed break-words text-foreground">
        {finding.summary}
      </h3>

      {finding.file_path && (
        <p className="break-all text-xs font-mono text-muted">
          <span className="font-semibold text-foreground/80">{finding.file_path}</span>
          {finding.line_start ? (
            <span>
              :{finding.line_start}
              {finding.line_end && finding.line_end !== finding.line_start
                ? `–${finding.line_end}`
                : ""}
            </span>
          ) : (
            <span className="italic ml-1">(file-level)</span>
          )}
        </p>
      )}

      {finding.suggestion && (
        <details className="rounded-lg border border-border bg-surface/50">
          <summary className="cursor-pointer px-3 py-2.5 text-xs font-medium text-foreground hover:bg-raised transition-colors">
            Suggested change
          </summary>
          <pre className="overflow-x-auto whitespace-pre-wrap break-words border-t border-border p-3 font-mono text-xs leading-relaxed text-foreground bg-panel">
            {finding.suggestion}
          </pre>
        </details>
      )}
    </article>
  );
}

export function FindingsByAgent({ findings }: { findings: Finding[] }) {
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  const filteredFindings = findings.filter((f) => {
    if (severityFilter === "all") return true;
    return (f.severity || "unknown").toLowerCase() === severityFilter.toLowerCase();
  });

  const groups = new Map<string, Finding[]>();
  for (const finding of filteredFindings) {
    const key = finding.agent_type || "unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(finding);
  }

  // Count per severity
  const severityCounts = {
    all: findings.length,
    critical: findings.filter((f) => (f.severity || "").toLowerCase() === "critical").length,
    high: findings.filter((f) => (f.severity || "").toLowerCase() === "high").length,
    medium: findings.filter((f) => (f.severity || "").toLowerCase() === "medium").length,
    low: findings.filter((f) => (f.severity || "").toLowerCase() === "low").length,
  };

  if (!findings.length) {
    return (
      <div className="rounded-xl border border-border bg-panel p-6 text-sm text-muted">
        No findings recorded for this review.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Findings Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-panel px-4 py-3 text-xs">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted font-medium mr-1">Filter severity:</span>
          {(["all", "critical", "high", "medium", "low"] as const).map((sev) => {
            const count = severityCounts[sev];
            const isSelected = severityFilter === sev;
            return (
              <button
                key={sev}
                type="button"
                onClick={() => setSeverityFilter(sev)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  isSelected
                    ? "bg-accent/20 text-accent border border-accent/40 font-semibold"
                    : "bg-surface text-muted hover:text-foreground border border-border"
                }`}
              >
                {sev.charAt(0).toUpperCase() + sev.slice(1)} ({count})
              </button>
            );
          })}
        </div>

        <p className="text-muted text-[11px] italic">
          Automated findings do not imply all code was examined.
        </p>
      </div>

      {filteredFindings.length === 0 ? (
        <div className="rounded-xl border border-border bg-panel p-6 text-center text-sm text-muted">
          No findings match the selected severity filter ({severityFilter}).
        </div>
      ) : (
        <div className="space-y-4">
          {[...groups.entries()].map(([agent, list]) => (
            <section
              key={agent}
              className="overflow-hidden rounded-xl border border-border bg-panel"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface/50 px-5 py-4">
                <h2 className="text-sm font-semibold text-foreground">
                  {AGENTS[agent] ?? agent.replaceAll("_", " ")}
                </h2>
                <span className="text-xs text-muted">
                  {list.length} finding{list.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="divide-y divide-border">
                {list.map((finding, idx) => (
                  <FindingCard key={finding.id || idx} finding={finding} index={idx} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
