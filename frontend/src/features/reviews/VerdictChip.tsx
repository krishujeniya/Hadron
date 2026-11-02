import clsx from "clsx";
import type { Verdict } from "@/lib/types";
const LABELS: Record<string, string> = { approve: "Approve", request_changes: "Request changes", dismiss: "Dismiss", comment: "Comment", needs_human_review: "Needs Human Review" };
export function VerdictChip({ verdict, className }: { verdict?: Verdict | string | null; className?: string }) {
  if (!verdict) return <span className="text-xs text-muted">Not available</span>;
  const value = verdict.toLowerCase();
  return <span className={clsx("inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium whitespace-nowrap", value === "approve" ? "border-ok/30 bg-ok/10 text-ok" : value === "request_changes" ? "border-warn/30 bg-warn/10 text-warn" : value === "needs_human_review" ? "border-amber-500/30 bg-amber-500/10 text-amber-400" : "border-border bg-surface text-muted", className)}>{LABELS[value] ?? verdict}</span>;
}
