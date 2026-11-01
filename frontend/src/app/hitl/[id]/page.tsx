"use client";

import useSWR from "swr";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FindingsByAgent } from "@/components/AgentFindingCard";
import { HITLDecisionForm } from "@/components/HITLDecisionForm";
import { VerdictChip } from "@/components/VerdictChip";
import { Empty } from "@/components/Empty";
import type { HITLDetail } from "@/lib/types";

export default function HITLDetailPage() {
  const params = useParams<{ id: string }>();
  const id = decodeURIComponent(params.id);
  const { data, error, isLoading } = useSWR<HITLDetail>(
    `/api/v1/hitl/${encodeURIComponent(id)}`
  );

  if (error) return <Empty>Failed to load: {error.message}</Empty>;
  if (isLoading || !data) return <Empty>Loading…</Empty>;

  const prUrl = `https://github.com/${data.repo_full_name}/pull/${data.pr_number}`;
  const isResolved = data.status !== "pending" && data.status !== "in_review";

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs font-mono text-muted">
        <Link href="/" className="hover:text-foreground transition-colors">Overview</Link>
        <span>/</span>
        <Link href="/hitl" className="hover:text-foreground transition-colors">Human review</Link>
        <span>/</span>
        <span className="text-foreground font-semibold">{data.repo_full_name} #{data.pr_number}</span>
      </nav>

      {/* Governance & Consequential Decision Callout */}
      <div className="p-3.5 rounded-xl border border-border bg-panel flex items-center gap-3 text-xs text-foreground">
        <svg className="w-4 h-4 text-accent shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
        <div>
          <span className="font-semibold text-foreground">Consequential Decision Gate: </span>
          Decisions recorded here are binding human determinations permanently attributed to your authenticated identity. Once submitted, decisions cannot be edited or overridden. Submitting does not merge the pull request.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-start justify-between gap-4 border-b border-separator pb-4">
            <div className="min-w-0">
              <div className="text-xs text-muted font-mono truncate">{data.review_id}</div>
              <h1 className="text-xl font-bold text-foreground mt-1 font-mono">
                {data.repo_full_name} #{data.pr_number}
              </h1>
              <p className="text-sm text-muted mt-1">{data.escalation_reason}</p>
              <a
                href={prUrl}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-accent underline mt-2 inline-block font-mono"
              >
                Open pull request on GitHub →
              </a>
            </div>
            <div className="flex flex-col items-end gap-1.5 shrink-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-muted font-mono">agent:</span>
                <VerdictChip verdict={data.agent_verdict} />
              </div>
              {data.human_verdict && (
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted font-mono">human:</span>
                  <VerdictChip verdict={data.human_verdict} />
                </div>
              )}
            </div>
          </div>

          <FindingsByAgent findings={data.findings ?? []} />

          {isResolved && data.human_reason && (
            <div className="border border-border rounded-xl bg-surface p-4 shadow-sm">
              <div className="text-xs uppercase tracking-wide text-muted font-mono mb-2">
                Human reason {data.reviewer_id ? `· by ${data.reviewer_id}` : ""}
              </div>
              <p className="text-sm whitespace-pre-wrap text-foreground">{data.human_reason}</p>
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {isResolved ? (
            <div className="border border-border rounded-xl bg-surface p-4 text-sm shadow-sm">
              <div className="text-xs uppercase tracking-wide text-muted font-mono mb-2">
                Resolution status
              </div>
              <div className="font-mono text-foreground font-semibold">{data.status}</div>
              {data.resolved_at && (
                <div className="text-xs text-muted mt-1 font-mono">
                  resolved {new Date(data.resolved_at).toLocaleString()}
                </div>
              )}
            </div>
          ) : (
            <div className="sticky top-6">
              <h2 className="text-sm uppercase tracking-wide text-muted font-mono font-semibold mb-3">
                Make a determination
              </h2>
              <HITLDecisionForm hitlId={data.id} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
