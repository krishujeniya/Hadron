"use client";

import { useState } from "react";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { FindingsByAgent } from "@/components/AgentFindingCard";
import { DiffViewer } from "@/components/DiffViewer";
import { ReviewStatusBadge } from "@/components/ReviewStatusBadge";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import { api } from "@/lib/api";
import type { ReviewDetail } from "@/lib/types";

export default function ReviewDetailPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"findings" | "diff">("findings");

  // Use api.getReview (custom fetcher) instead of the URL-string fetcher so
  // the BE-route fallback in lib/api.ts kicks in for ids containing "/".
  const { data, error, isLoading } = useSWR<ReviewDetail>(
    ["review-detail", id],
    () => api.getReview(id),
    { refreshInterval: 5000 }
  );

  if (error) return <Empty>Failed to load: {error.message}</Empty>;
  if (isLoading || !data) return <Empty>Loading…</Empty>;

  const prUrl = `https://github.com/${data.repo_full_name}/pull/${data.pr_number}`;

  const copyMarkdown = () => {
    if (!data) return;
    const findingsMd = (data.findings || []).map(f => {
      const loc = f.file_path ? `\`${f.file_path}${f.line_start ? `:${f.line_start}` : ""}\`` : "General";
      const sugg = f.suggestion ? `\n> **Suggestion:**\n> \`\`\`\n> ${f.suggestion}\n> \`\`\`` : "";
      return `### [${(f.severity || "info").toUpperCase()}] ${f.summary}\n- **Agent:** ${f.agent_type}\n- **Location:** ${loc}\n- **Confidence:** ${((f.confidence ?? 0.5) * 100).toFixed(0)}%${sugg}\n`;
    }).join("\n");

    const md = `# Hadron Review: ${data.repo_full_name} #${data.pr_number}\n\n**Verdict:** ${data.verdict || "PENDING"}\n**Overall Confidence:** ${((data.overall_confidence ?? 0) * 100).toFixed(0)}%\n**Commit:** \`${data.head_commit_sha}\`\n\n## Findings\n\n${findingsMd || "No issues found."}\n\n---\n*Reviewed autonomously by [Hadron](https://hadron.dev)*`;

    navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs text-muted font-mono truncate">{data.id}</div>
          <h1 className="text-2xl font-semibold mt-1">
            {data.repo_full_name} #{data.pr_number}
          </h1>
          <div className="text-sm text-muted mt-1">{data.pr_title}</div>
          <div className="text-xs text-muted font-mono mt-2">
            {data.head_commit_sha}
          </div>
          <div className="flex items-center gap-3 mt-3">
            <a
              href={prUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-accent hover:underline inline-flex items-center gap-1"
            >
              Open PR on GitHub →
            </a>
            <button
              onClick={copyMarkdown}
              className="px-2.5 py-1 bg-surface border border-border hover:border-accent/40 text-xs font-medium text-foreground/80 hover:text-foreground rounded transition-colors"
            >
              {copied ? "✓ Copied Markdown" : "📋 Copy Review as Markdown"}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <ReviewStatusBadge status={data.status} />
          <VerdictChip verdict={data.verdict} />
        </div>
      </div>

      {data.overall_confidence != null && (
        <div className="text-xs text-muted">
          Overall confidence: {(data.overall_confidence * 100).toFixed(0)}%
        </div>
      )}

      {/* View Mode Tabs */}
      <div className="flex items-center gap-2 border-b border-border pb-1">
        <button
          onClick={() => setActiveTab("findings")}
          className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-t-lg transition-colors border-b-2 -mb-[5px] ${
            activeTab === "findings"
              ? "border-accent text-accent bg-panel font-semibold"
              : "border-transparent text-muted hover:text-foreground"
          }`}
        >
          <span>Findings Breakdown</span>
          <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-surface text-muted">
            {data.findings?.length ?? 0}
          </span>
        </button>
        <button
          onClick={() => setActiveTab("diff")}
          className={`flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-t-lg transition-colors border-b-2 -mb-[5px] ${
            activeTab === "diff"
              ? "border-accent text-accent bg-panel font-semibold"
              : "border-transparent text-muted hover:text-foreground"
          }`}
        >
          <span>Interactive Diff Viewer</span>
          <span className="text-[10px] font-mono opacity-70">
            [Inline Annotations]
          </span>
        </button>
      </div>

      {activeTab === "findings" ? (
        <FindingsByAgent findings={data.findings ?? []} />
      ) : (
        <DiffViewer diff={data.pr_diff || undefined} findings={data.findings ?? []} />
      )}

      {data.human_review_reason && (
        <div className="border border-border rounded-lg bg-panel p-4">
          <div className="text-xs uppercase tracking-wide text-muted mb-2">
            Human review reason
          </div>
          <p className="text-sm whitespace-pre-wrap">{data.human_review_reason}</p>
        </div>
      )}
    </div>
  );
}
