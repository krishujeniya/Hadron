import clsx from "clsx";
export function SeverityChip({ severity }: { severity: string }) {
  const value = (severity || "unknown").toLowerCase();
  return <span className={clsx("inline-flex shrink-0 items-center rounded-md border px-2 py-1 text-xs font-medium capitalize", ["critical", "high", "major"].includes(value) ? "border-err/30 bg-err/10 text-err" : ["medium", "minor"].includes(value) ? "border-warn/30 bg-warn/10 text-warn" : "border-border bg-surface text-muted")}>{value}</span>;
}
