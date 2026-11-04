"use client";

import { useState } from "react";
import useSWR from "swr";
import { useGitHubAccount } from "@/features/auth/github-context";
import { Empty } from "@/components/ui/Empty";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import type {
  BudgetStatus,
  DailyPoint,
  EconomicsSummary,
} from "@/lib/types";

export default function EconomicsPage() {
  const { currentAccount } = useGitHubAccount();
  const [showTableView, setShowTableView] = useState(false);

  const accountQuery = currentAccount ? `account=${encodeURIComponent(currentAccount.login)}` : "";
  const summaryUrl = `/api/v1/economics/summary${accountQuery ? `?${accountQuery}` : ""}`;
  const budgetUrl = `/api/v1/economics/budget${accountQuery ? `?${accountQuery}` : ""}`;
  const timeseriesUrl = `/api/v1/economics/timeseries?days=30${accountQuery ? `&${accountQuery}` : ""}`;

  const { data: summary, error: sumErr, isLoading: sumLoading, mutate: mutateSummary } =
    useSWR<EconomicsSummary>(summaryUrl);
  const { data: budget, error: budErr, isLoading: budLoading, mutate: mutateBudget } =
    useSWR<BudgetStatus>(budgetUrl);
  const { data: timeseries, error: tsErr, isLoading: tsLoading, mutate: mutateTimeseries } =
    useSWR<DailyPoint[]>(timeseriesUrl);

  const exportCsv = () => {
    if (!timeseries || timeseries.length === 0) return;
    const header = "Date (UTC),Cost (USD),LLM Calls\n";
    const rows = timeseries
      .map((p) => `${p.date},${p.cost_usd.toFixed(4)},${p.call_count}`)
      .join("\n");
    const blob = new Blob([header + rows], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `hadron-usage-${currentAccount?.login || "workspace"}-30d.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-8">
      <PageHeader
        tag={currentAccount ? `Workspace @${currentAccount.login}` : "Operations & Cost Ledger"}
        title="Usage & Cost Control"
        description="LLM token spend, budget headroom, and per-model cost attribution. Settled records in UTC currency (USD)."
        actions={
          <div className="flex items-center gap-2">
            {timeseries && timeseries.length > 0 && (
              <Button variant="outline" size="sm" onClick={exportCsv} className="text-xs">
                Export Ledger (CSV)
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void mutateSummary();
                void mutateBudget();
                void mutateTimeseries();
              }}
              className="text-xs"
            >
              Refresh
            </Button>
          </div>
        }
      />

      {/* Autonomous Cloud Guardrails Banner */}
      <div className="p-4 rounded-xl border border-border bg-panel flex items-start sm:items-center gap-3 text-xs text-foreground">
        <svg className="w-4 h-4 text-accent shrink-0 mt-0.5 sm:mt-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
        <div>
          <span className="font-semibold text-foreground">Tenant cost guardrails: </span>
          Hadron enforces strict daily spend reservations and advisory per-review budget ceilings.
          Usage metrics are settled against PostgreSQL ledger records in UTC. Provider calls are bounded
          automatically to prevent runaway token spend.
        </div>
      </div>

      {/* Budget gauge */}
      <section className="border border-border rounded-xl bg-panel p-5 shadow-sm space-y-3">
        <div className="flex items-baseline justify-between">
          <div className="text-xs uppercase tracking-wider text-muted font-mono font-semibold">
            Daily Budget Ceiling (UTC)
          </div>
          <div className="text-xs text-muted font-mono">
            {budget
              ? `${pct(budget.daily_utilization)} used`
              : budErr
              ? "Telemetry unavailable"
              : "Checking budget…"}
          </div>
        </div>

        {budErr ? (
          <div role="alert" className="rounded-lg border border-err/30 bg-err/10 p-4 text-xs text-err">
            Could not retrieve budget status: {String(budErr.message || "Server error")}.
          </div>
        ) : budLoading || !budget ? (
          <div className="h-3 rounded bg-surface border border-border animate-pulse" />
        ) : (
          <>
            <div
              role="progressbar"
              aria-label="Daily budget usage"
              aria-valuenow={Math.round(budget.daily_utilization * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
              className="h-3 rounded bg-surface border border-border overflow-hidden"
            >
              <div
                className={`h-full transition-all ${
                  budget.exceeded
                    ? "bg-err"
                    : budget.daily_utilization > 0.8
                    ? "bg-warn"
                    : "bg-primary-action"
                }`}
                style={{
                  width: `${Math.min(100, budget.daily_utilization * 100)}%`,
                }}
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm font-mono pt-1">
              <span className={budget.exceeded ? "text-err font-bold" : "text-foreground font-semibold"}>
                {usd(budget.daily_spent_usd)} spent today
              </span>
              <span className="text-muted text-xs">
                Hard ceiling: <strong className="text-foreground">{usd(budget.daily_cap_usd)}</strong> · Headroom:{" "}
                <strong className="text-foreground">{usd(budget.daily_headroom_usd)}</strong>
              </span>
            </div>
            <div className="text-[11px] text-muted flex flex-wrap items-center gap-2 pt-1 border-t border-border">
              <span>Per-review advisory ceiling: {usd(budget.per_review_cap_usd)}</span>
              <span>•</span>
              <span>Status: <strong className="font-mono text-foreground">{budget.ledger_status}</strong></span>
              {budget.exceeded && (
                <span className="text-err font-semibold">
                  · Daily cap exceeded: new provider calls halted
                </span>
              )}
            </div>
          </>
        )}
      </section>

      {/* Spend cards */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat
          label="Today (UTC)"
          value={summary ? usd(summary.today_usd) : undefined}
          err={!!sumErr}
          loading={sumLoading}
          sub="Settled spend today"
        />
        <Stat
          label="Last 7 days"
          value={summary ? usd(summary.last_7d_usd) : undefined}
          err={!!sumErr}
          loading={sumLoading}
          sub="Rolling 7-day total"
        />
        <Stat
          label="Last 30 days"
          value={summary ? usd(summary.last_30d_usd) : undefined}
          err={!!sumErr}
          loading={sumLoading}
          sub={
            summary
              ? `${summary.call_count_30d} provider calls · ${fmtTokens(
                  summary.total_input_tokens_30d + summary.total_output_tokens_30d
                )} tokens`
              : undefined
          }
        />
      </section>

      {/* 30-Day Daily Spend Section (Chart + Accessible Table) */}
      <section className="border border-border rounded-xl bg-panel p-5 space-y-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground font-mono">Daily Spend Trend (30 Days)</h2>
            <p className="text-xs text-muted">Dense UTC daily timeline aggregated across authorized review runs.</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowTableView(!showTableView)}
            className="text-xs"
          >
            {showTableView ? "Show Sparkline View" : "Show Accessible Table"}
          </Button>
        </div>

        {tsErr ? (
          <div role="alert" className="p-4 rounded-lg border border-err/30 bg-err/10 text-xs text-err">
            Could not load timeseries telemetry: {String(tsErr.message || "Server error")}.
          </div>
        ) : tsLoading ? (
          <Empty>
            <span role="status" className="text-muted">Loading 30-day spend telemetry…</span>
          </Empty>
        ) : !timeseries || timeseries.length === 0 ? (
          <Empty>No usage recorded for this workspace in the last 30 days.</Empty>
        ) : showTableView ? (
          <div
            role="region"
            aria-label="30-day daily spend table"
            tabIndex={0}
            className="overflow-x-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <table className="w-full text-xs font-mono">
              <thead className="border-b border-border text-muted bg-surface/50">
                <tr>
                  <th scope="col" className="px-4 py-2.5 text-left font-medium">Date (UTC)</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">Spend (USD)</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">LLM Calls</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {timeseries.map((pt) => (
                  <tr key={pt.date} className="hover:bg-surface/50">
                    <td className="px-4 py-2 text-foreground">{pt.date}</td>
                    <td className="px-4 py-2 text-right text-foreground font-semibold">
                      {usd(pt.cost_usd)}
                    </td>
                    <td className="px-4 py-2 text-right text-muted">{pt.call_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Sparkline points={timeseries} />
        )}
      </section>

      {/* Breakdown tables */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Breakdown
          title="Spend by Model (30d)"
          rows={summary?.by_model_30d}
          total={summary?.last_30d_usd}
          err={!!sumErr}
          loading={sumLoading}
        />
        <Breakdown
          title="Spend by Specialist Agent (30d)"
          rows={summary?.by_agent_30d}
          total={summary?.last_30d_usd}
          err={!!sumErr}
          loading={sumLoading}
        />
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  err,
  loading,
}: {
  label: string;
  value?: string;
  sub?: string;
  err?: boolean;
  loading?: boolean;
}) {
  return (
    <div className="border border-border rounded-xl bg-panel px-4 py-3 shadow-sm hover:border-muted/50 hover:-translate-y-0.5 transition-all duration-150">
      <div className="text-xs uppercase tracking-wide text-muted font-mono">{label}</div>
      <div className="text-2xl font-mono font-bold mt-1 text-foreground">
        {err ? "Telemetry error" : loading ? "…" : value ?? "$0.00"}
      </div>
      {sub && <div className="text-[11px] text-muted mt-1 font-mono">{sub}</div>}
    </div>
  );
}

function Breakdown({
  title,
  rows,
  total,
  err,
  loading,
}: {
  title: string;
  rows?: Record<string, number>;
  total?: number;
  err?: boolean;
  loading?: boolean;
}) {
  const entries = rows ? Object.entries(rows).sort((a, b) => b[1] - a[1]) : [];
  return (
    <div className="border border-border rounded-xl bg-panel shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-border text-xs font-semibold text-foreground font-mono uppercase tracking-wider">
        {title}
      </div>
      {err ? (
        <div className="px-4 py-3 text-xs text-err">Telemetry unavailable</div>
      ) : loading || !rows ? (
        <div className="px-4 py-3 text-xs text-muted">Loading breakdown…</div>
      ) : entries.length === 0 ? (
        <div className="px-4 py-3 text-xs text-muted">No usage recorded.</div>
      ) : (
        <div className="divide-y divide-border">
          {entries.map(([k, v]) => {
            const share = total && total > 0 ? v / total : 0;
            return (
              <div
                key={k}
                className="flex items-center justify-between px-4 py-2.5 gap-3 hover:bg-surface/50 transition-colors min-w-0"
              >
                <div className="font-mono text-xs text-foreground truncate min-w-0 flex-1">{k}</div>
                <div className="flex items-center gap-3 shrink-0">
                  <div className="w-20 sm:w-24 h-1.5 rounded bg-surface overflow-hidden">
                    <div
                      className="h-full bg-accent"
                      style={{ width: `${Math.min(100, share * 100)}%` }}
                    />
                  </div>
                  <div className="font-mono text-xs w-20 text-right text-foreground font-medium">
                    {usd(v)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Sparkline({ points }: { points: DailyPoint[] }) {
  const data = [...points].sort((a, b) => a.date.localeCompare(b.date));
  const W = 800;
  const H = 140;
  const PAD = 12;
  const max = Math.max(0.0001, ...data.map((p) => p.cost_usd));
  const stepX = data.length > 1 ? (W - 2 * PAD) / (data.length - 1) : 0;
  const y = (v: number) => H - PAD - (v / max) * (H - 2 * PAD);
  const path = data
    .map((p, i) => `${i === 0 ? "M" : "L"} ${PAD + i * stepX} ${y(p.cost_usd)}`)
    .join(" ");

  return (
    <div className="space-y-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-36 stroke-accent fill-none"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path d={path} strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="flex justify-between text-[11px] text-muted font-mono">
        <span>{data[0]?.date ?? ""}</span>
        <span>Peak: {usd(max)}/day</span>
        <span>{data[data.length - 1]?.date ?? ""}</span>
      </div>
    </div>
  );
}

function usd(v: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(v);
}

function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
