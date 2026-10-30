import { SeverityChip } from "./SeverityChip";
import type { Finding } from "@/lib/types";
const AGENTS: Record<string, string> = { security: "Security", quality: "Code quality", test_coverage: "Test coverage", documentation: "Documentation" };
export function FindingCard({ finding }: { finding: Finding }) {
  const confidence = Number.isFinite(finding.confidence) ? `${Math.round(finding.confidence * 100)}%` : "Not available";
  return (
    <article className="px-4 py-5 sm:px-5 space-y-3">
      <div className="flex flex-wrap items-center gap-2"><SeverityChip severity={finding.severity} /><span className="text-xs text-muted">Model confidence: {confidence}</span></div>
      <h3 className="text-sm font-medium leading-relaxed break-words">{finding.summary}</h3>
      {finding.file_path && <p className="break-all text-xs font-mono text-muted">{finding.file_path}{finding.line_start ? `:${finding.line_start}` : ""}{finding.line_end && finding.line_end !== finding.line_start ? `–${finding.line_end}` : ""}</p>}
      {finding.suggestion && <details className="rounded-lg border border-border bg-bg"><summary className="cursor-pointer px-3 py-3 text-sm font-medium">Suggested change</summary><pre className="overflow-x-auto whitespace-pre-wrap break-words border-t border-border p-3 font-mono text-xs leading-relaxed">{finding.suggestion}</pre></details>}
    </article>
  );
}
export function FindingsByAgent({ findings }: { findings: Finding[] }) {
  const groups = new Map<string, Finding[]>();
  for (const finding of findings) { const key = finding.agent_type || "unknown"; if (!groups.has(key)) groups.set(key, []); groups.get(key)!.push(finding); }
  if (!groups.size) return <div className="rounded-xl border border-border bg-panel p-6 text-sm text-muted">No findings recorded for this review.</div>;
  return <div className="space-y-4">{[...groups.entries()].map(([agent, list]) => <section key={agent} className="overflow-hidden rounded-xl border border-border bg-panel"><div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface/40 px-5 py-4"><h2 className="text-sm font-semibold">{AGENTS[agent] ?? agent.replaceAll("_", " ")}</h2><span className="text-xs text-muted">{list.length} finding{list.length === 1 ? "" : "s"}</span></div><div className="divide-y divide-border">{list.map((finding) => <FindingCard key={finding.id} finding={finding} />)}</div></section>)}</div>;
}
