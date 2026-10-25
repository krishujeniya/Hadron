import clsx from "clsx";
import type { ReviewStatus } from "@/lib/types";

const COLORS: Record<string, string> = {
  queued: "bg-zinc-900 text-zinc-400 border border-zinc-800",
  in_progress: "bg-gradient-to-r from-white/15 to-white/5 text-white border border-white/30 animate-pulse",
  agents_running: "bg-gradient-to-r from-white/15 to-white/5 text-white border border-white/30 animate-pulse",
  aggregating: "bg-gradient-to-r from-zinc-800 to-zinc-900 text-zinc-200 border border-zinc-700",
  posting: "bg-zinc-800 text-zinc-200 border border-zinc-700",
  completed: "bg-white/10 text-white border border-white/20 font-medium",
  escalated: "bg-zinc-800 text-zinc-300 border border-zinc-700 font-semibold",
  failed: "bg-black text-zinc-400 border border-zinc-800",
};

export function ReviewStatusBadge({ status }: { status: ReviewStatus | string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-mono",
        COLORS[status] ?? "bg-panel text-muted"
      )}
    >
      {status}
    </span>
  );
}
