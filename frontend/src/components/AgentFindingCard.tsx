import { SeverityChip } from "./SeverityChip";
import type { Finding } from "@/lib/types";

export function FindingCard({ finding }: { finding: Finding }) {
  return (
    <div className="px-4 py-3 space-y-1">
      <div className="flex items-start gap-2">
        <SeverityChip severity={finding.severity} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium">{finding.summary}</div>
          {finding.file_path && (
            <div className="text-xs font-mono text-muted truncate">
              {finding.file_path}
              {finding.line_start ? `:${finding.line_start}` : ""}
              {finding.line_end && finding.line_end !== finding.line_start
                ? `-${finding.line_end}`
                : ""}
            </div>
          )}
        </div>
        <span className="text-xs text-muted shrink-0">
          conf {(finding.confidence * 100).toFixed(0)}%
        </span>
      </div>
      {finding.suggestion && (
        <div className="mt-2 text-xs border-l-2 border-white/60 pl-3 space-y-1">
          <div className="text-white font-semibold text-[11px] uppercase tracking-wider">Recommendation</div>
          <pre className="bg-black border border-white/10 rounded p-2 font-mono text-[11px] text-foreground/90 overflow-x-auto whitespace-pre-wrap">
            {finding.suggestion}
          </pre>
        </div>
      )}
    </div>
  );
}

export function FindingsByAgent({ findings }: { findings: Finding[] }) {
  const groups = new Map<string, Finding[]>();
  for (const f of findings) {
    const k = f.agent_type || "unknown";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(f);
  }
  if (groups.size === 0) {
    return (
      <div className="border border-white/10 rounded-xl bg-panel px-4 py-3 text-sm text-muted">
        No findings.
      </div>
    );
  }
  return (
    <div className="grid gap-4">
      {[...groups.entries()].map(([agent, list]) => (
        <div key={agent} className="border border-white/10 rounded-xl bg-gradient-to-b from-zinc-900/50 to-black overflow-hidden shadow-sm">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-white/[0.02]">
            <span className="font-mono text-sm font-semibold text-white uppercase tracking-wider">{agent}</span>
            <span className="text-xs text-muted font-mono">
              {list.length} finding{list.length === 1 ? "" : "s"}
            </span>
          </div>
          <div className="divide-y divide-white/10">
            {list.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
