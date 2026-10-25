import clsx from "clsx";

const COLORS: Record<string, string> = {
  info: "bg-zinc-900 text-zinc-400 border border-zinc-800",
  low: "bg-zinc-900 text-zinc-300 border border-zinc-700",
  medium: "bg-zinc-800 text-zinc-200 border border-zinc-600",
  high: "bg-zinc-800 text-white border border-zinc-500 font-semibold",
  critical: "bg-gradient-to-r from-white to-zinc-200 text-black border border-white font-bold shadow-sm shadow-white/10",
};

export function SeverityChip({ severity }: { severity: string }) {
  const k = (severity ?? "").toLowerCase();
  return (
    <span
      className={clsx(
        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono uppercase tracking-wide",
        COLORS[k] ?? "bg-panel text-muted"
      )}
    >
      {severity}
    </span>
  );
}
