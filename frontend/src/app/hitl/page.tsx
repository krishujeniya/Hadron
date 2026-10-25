"use client";

import useSWR from "swr";
import Link from "next/link";
import { useGitHubAccount } from "@/lib/githubContext";
import { Empty } from "@/components/Empty";
import { VerdictChip } from "@/components/VerdictChip";
import type { HITLItem, Paginated } from "@/lib/types";

export default function HITLQueuePage() {
  const { currentAccount } = useGitHubAccount();

  const accountParam = currentAccount ? `&account=${encodeURIComponent(currentAccount.login)}` : "";
  const { data, error, isLoading } =
    useSWR<Paginated<HITLItem>>(`/api/v1/hitl/queue?limit=100${accountParam}`);

  const rawItems = data?.items ?? [];
  const items = currentAccount
    ? rawItems.filter((h) => h.repo_full_name.toLowerCase().startsWith(`${currentAccount.login.toLowerCase()}/`))
    : rawItems;
  const pending = items.filter((h) => h.status === "pending" || h.status === "in_review");

  return (
    <div className="space-y-6">
      {/* Header & Context */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
              Approvals & Sign-Offs
            </h1>
            {currentAccount && (
              <span className="font-mono text-xs text-white bg-white/10 border border-white/20 px-2 py-0.5 rounded-full">
                @{currentAccount.login}
              </span>
            )}
          </div>
          <p className="text-zinc-400 text-sm mt-1">
            {currentAccount
              ? `Pull requests requiring human review for repositories under @${currentAccount.login}.`
              : "Pull requests escalated for human review across your connected repositories."}
          </p>
        </div>

        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-black/60 border border-white/10 text-xs font-mono text-zinc-300">
          <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
          <span>{pending.length} pending approval{pending.length === 1 ? "" : "s"}</span>
        </div>
      </div>

      {/* Psychological Safety Banner */}
      <div className="p-3.5 rounded-xl border border-white/10 bg-white/[0.02] flex items-center gap-3 text-xs text-zinc-300">
        <span className="text-base shrink-0">🛡️</span>
        <div>
          <span className="font-semibold text-white">Safe Governance Guarantee: </span>
          Hadron's multi-agent review is non-destructive. Reviewing or approving pull requests here will not delete code, mutate databases, or interrupt live users.
        </div>
      </div>

      {error ? (
        <Empty>Failed to load: {error.message}</Empty>
      ) : isLoading ? (
        <Empty>Loading pending approvals…</Empty>
      ) : pending.length === 0 ? (
        <div className="border border-white/10 rounded-2xl bg-gradient-to-b from-zinc-900/40 to-black p-8 text-center space-y-3">
          <div className="text-3xl">🎉</div>
          <h3 className="text-base font-bold text-white">Approvals Queue is Clear</h3>
          <p className="text-xs text-zinc-400 max-w-md mx-auto">
            All pull requests for {currentAccount ? `@${currentAccount.login}` : "your workspace"} have passed autonomous screening. No manual approvals are currently blocking deployment.
          </p>
        </div>
      ) : (
        <div className="border border-white/10 rounded-2xl bg-panel divide-y divide-white/10 overflow-hidden shadow-sm">
          {pending.map((h) => (
            <Link
              key={h.id}
              href={`/hitl/${encodeURIComponent(h.id)}`}
              className="flex items-start justify-between px-5 py-4 hover:bg-white/[0.03] transition-all gap-4 group"
            >
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-white group-hover:underline">
                    {h.repo_full_name} #{h.pr_number}
                  </span>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-white/10 text-zinc-300 border border-white/10">
                    Needs Sign-Off
                  </span>
                </div>
                <div className="text-sm text-zinc-300 leading-snug">
                  {h.escalation_reason}
                </div>
                <div className="text-xs text-zinc-500 font-mono">
                  Agent Confidence: {(h.overall_confidence * 100).toFixed(0)}% ·{" "}
                  Escalated {new Date(h.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="shrink-0 flex items-center gap-2 pt-1">
                <VerdictChip verdict={h.agent_verdict} />
                <span className="text-xs font-medium text-white group-hover:translate-x-0.5 transition-transform">
                  Review →
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
