import clsx from "clsx";
import type { Verdict } from "@/lib/types";

const COLORS: Record<string, string> = {
  approve: "bg-gradient-to-r from-white/20 to-white/5 text-white border-white/40 font-semibold shadow-sm",
  request_changes: "bg-gradient-to-r from-zinc-800 to-zinc-900 text-zinc-100 border-zinc-600 font-semibold",
  dismiss: "bg-black text-zinc-400 border-zinc-800",
  comment: "bg-zinc-900 text-zinc-200 border-zinc-700",
};

const LABELS: Record<string, string> = {
  approve: "Approve",
  request_changes: "Request changes",
  dismiss: "Dismiss",
  comment: "Comment",
};

export function VerdictChip({
  verdict,
  className,
}: {
  verdict?: Verdict | string | null;
  className?: string;
}) {
  if (!verdict) return null;
  const v = verdict as string;
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium",
        COLORS[v] ?? "bg-panel text-muted border-border",
        className
      )}
    >
      {LABELS[v] ?? v}
    </span>
  );
}
