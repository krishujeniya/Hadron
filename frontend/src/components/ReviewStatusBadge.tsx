import clsx from "clsx";
import type { ReviewStatus } from "@/lib/types";

const LABELS: Record<string, string> = { queued: "Queued", received: "Received", in_progress: "In progress", agents_running: "Reviewing", aggregating: "Combining findings", posting: "Posting review", completed: "Completed", escalated: "Needs review", failed: "Failed" };
export function ReviewStatusBadge({ status }: { status: ReviewStatus | string }) {
  return <span className={clsx("inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium whitespace-nowrap", status === "failed" ? "border-err/30 bg-err/10 text-err" : status === "escalated" ? "border-warn/30 bg-warn/10 text-warn" : status === "completed" ? "border-ok/30 bg-ok/10 text-ok" : "border-border bg-surface text-muted")}>{LABELS[status] ?? status.replaceAll("_", " ")}</span>;
}
