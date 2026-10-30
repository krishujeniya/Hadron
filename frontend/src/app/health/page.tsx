"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { HealthLiveResponse, HealthStatusResponse } from "@/lib/types";

export default function HealthPage() {
  const { data: liveData, error: liveError } = useSWR<HealthLiveResponse>(
    "/health/live",
    fetcher,
    { refreshInterval: 5000 }
  );

  const { data: readyData, error: readyError } = useSWR<HealthStatusResponse>(
    "/health/ready",
    fetcher,
    { refreshInterval: 5000 }
  );

  const isLive = Boolean(liveData?.status === "ok" && !liveError);
  const isPipelineReady = Boolean(readyData?.pipeline_ready);
  const isTigerDegraded = Boolean(
    readyData?.services?.tiger && readyData.services.tiger.includes("degraded")
  );

  return (
    <div className="space-y-6 max-w-5xl mx-auto p-4 sm:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">System Health & Capability</h1>
          <p className="text-sm text-muted">
            Live telemetry distinguishing HTTP process availability from operational review execution capability.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs px-2.5 py-1 rounded-full border border-border bg-panel text-muted font-mono">
            v{readyData?.version || liveData?.version || "0.13.0"}
          </span>
          <span className="text-xs px-2.5 py-1 rounded-full border border-border bg-panel text-muted font-mono">
            {readyData?.env || "production"}
          </span>
        </div>
      </div>

      {/* Main Operational Capability Banner */}
      <div className="border border-border rounded-xl bg-panel p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-muted font-semibold mb-1">
              Overall Review Pipeline State
            </div>
            <div className="text-lg font-mono font-medium flex items-center gap-2">
              {!isLive ? (
                <span className="text-err flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-err inline-block animate-pulse" />
                  API OFFLINE — Server Unreachable
                </span>
              ) : isPipelineReady ? (
                <span className="text-ok flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-ok inline-block" />
                  OPERATIONAL — Autonomous Review Pipeline Active
                </span>
              ) : (
                <span className="text-amber-500 flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-amber-500 inline-block animate-pulse" />
                  PIPELINE DEGRADED — API Online, Execution Capability Offline
                </span>
              )}
            </div>
            <p className="text-xs text-muted mt-1.5">
              {!isLive
                ? "HTTP liveness probe failed. Review requests cannot be accepted."
                : isPipelineReady
                ? "All critical dependencies (Postgres, Schema, Redis, and Worker fleet) are operational."
                : "Answering HTTP requests does not constitute an operating review pipeline. Review workers or queue must be online."}
            </p>
          </div>
          {isTigerDegraded && (
            <div className="px-3 py-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-400 text-xs font-mono">
              Vector RAG Degraded (Soft Fallback)
            </div>
          )}
        </div>
      </div>

      {/* Subsystem Health Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* API Server */}
        <div className="border border-border rounded-lg bg-panel p-4 flex flex-col justify-between">
          <div>
            <div className="text-xs text-muted font-semibold uppercase tracking-wider mb-2">
              API Server (Liveness)
            </div>
            <div className="text-sm font-mono flex items-center gap-2">
              {isLive ? (
                <span className="text-ok font-semibold">● ONLINE</span>
              ) : (
                <span className="text-err font-semibold">● UNREACHABLE</span>
              )}
            </div>
          </div>
          <div className="text-xs text-muted mt-3 pt-3 border-t border-border/50">
            Probe: /health/live (Zero external network calls)
          </div>
        </div>

        {/* Database & Schema */}
        <div className="border border-border rounded-lg bg-panel p-4 flex flex-col justify-between">
          <div>
            <div className="text-xs text-muted font-semibold uppercase tracking-wider mb-2">
              PostgreSQL & Schema
            </div>
            <div className="text-sm font-mono space-y-1">
              <div className="flex justify-between">
                <span className="text-muted">Connection:</span>
                <span
                  className={
                    readyData?.services?.postgres === "ok" ? "text-ok" : "text-err"
                  }
                >
                  {readyData?.services?.postgres || (readyError ? "unhealthy" : "checking…")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Schema DDL:</span>
                <span
                  className={
                    readyData?.services?.schema === "ok" ? "text-ok" : "text-err"
                  }
                >
                  {readyData?.services?.schema || (readyError ? "unmigrated" : "checking…")}
                </span>
              </div>
            </div>
          </div>
          <div className="text-xs text-muted mt-3 pt-3 border-t border-border/50">
            Source of record for reviews, findings, ledger
          </div>
        </div>

        {/* Redis & Job Queue */}
        <div className="border border-border rounded-lg bg-panel p-4 flex flex-col justify-between">
          <div>
            <div className="text-xs text-muted font-semibold uppercase tracking-wider mb-2">
              Redis Queue & State
            </div>
            <div className="text-sm font-mono space-y-1">
              <div className="flex justify-between">
                <span className="text-muted">Connectivity:</span>
                <span
                  className={
                    readyData?.services?.redis === "ok" ? "text-ok" : "text-err"
                  }
                >
                  {readyData?.services?.redis || (readyError ? "unhealthy" : "checking…")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Queue Backlog:</span>
                <span className="text-foreground">
                  {readyData?.queue?.depth ?? 0} jobs
                </span>
              </div>
            </div>
          </div>
          <div className="text-xs text-muted mt-3 pt-3 border-t border-border/50">
            Durable webhook idempotency & review dispatch
          </div>
        </div>

        {/* Worker Fleet Capability */}
        <div className="border border-border rounded-lg bg-panel p-4 flex flex-col justify-between">
          <div>
            <div className="text-xs text-muted font-semibold uppercase tracking-wider mb-2">
              Review Worker Fleet
            </div>
            <div className="text-sm font-mono space-y-1">
              <div className="flex justify-between">
                <span className="text-muted">Fleet Heartbeat:</span>
                <span
                  className={
                    readyData?.services?.worker === "ok" ? "text-ok" : "text-amber-500"
                  }
                >
                  {readyData?.services?.worker || "offline"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Active Workers:</span>
                <span className="text-foreground">
                  {readyData?.queue?.active_workers ?? 0} online
                </span>
              </div>
            </div>
          </div>
          <div className="text-xs text-muted mt-3 pt-3 border-t border-border/50">
            Heartbeat TTL: 45s (auto-eviction on crash)
          </div>
        </div>

        {/* Queue Latency / Oldest Job */}
        <div className="border border-border rounded-lg bg-panel p-4 flex flex-col justify-between">
          <div>
            <div className="text-xs text-muted font-semibold uppercase tracking-wider mb-2">
              Oldest Accepted Job
            </div>
            <div className="text-sm font-mono">
              <div className="text-xl font-bold text-foreground">
                {readyData?.queue?.oldest_accepted_job_age_seconds != null
                  ? `${readyData.queue.oldest_accepted_job_age_seconds.toFixed(1)}s`
                  : "0.0s"}
              </div>
              <span className="text-xs text-muted">
                {readyData?.queue?.oldest_accepted_job_age_seconds != null
                  ? "Time waiting in queue before worker pickup"
                  : "No waiting jobs in queue (healthy)"}
              </span>
            </div>
          </div>
          <div className="text-xs text-muted mt-3 pt-3 border-t border-border/50">
            SLO Threshold: &lt; 30s queue wait
          </div>
        </div>

        {/* Tiger Cloud / Vector Memory */}
        <div className="border border-border rounded-lg bg-panel p-4 flex flex-col justify-between">
          <div>
            <div className="text-xs text-muted font-semibold uppercase tracking-wider mb-2">
              Tiger Memory (RAG)
            </div>
            <div className="text-sm font-mono space-y-1">
              <div className="flex justify-between">
                <span className="text-muted">Status:</span>
                <span
                  className={
                    readyData?.services?.tiger?.startsWith("ok")
                      ? "text-ok"
                      : "text-amber-500"
                  }
                >
                  {readyData?.services?.tiger || "unconfigured"}
                </span>
              </div>
            </div>
          </div>
          <div className="text-xs text-muted mt-3 pt-3 border-t border-border/50">
            Optional vector store (reviews proceed if offline)
          </div>
        </div>
      </div>

      {/* Circuit Breakers */}
      {readyData?.circuit_breakers && readyData.circuit_breakers.length > 0 && (
        <div className="border border-border rounded-xl bg-panel p-5 space-y-3">
          <div className="text-xs uppercase tracking-wider text-muted font-semibold">
            Agent Circuit Breakers
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            {readyData.circuit_breakers.map((b) => (
              <div
                key={b.name}
                className="border border-border rounded-lg p-3 bg-background flex flex-col justify-between"
              >
                <div className="font-mono text-xs font-semibold text-foreground truncate">
                  {b.name}
                </div>
                <div className="flex items-center justify-between mt-2 text-xs font-mono">
                  <span
                    className={
                      b.state === "CLOSED"
                        ? "text-ok"
                        : b.state === "OPEN"
                        ? "text-err font-bold"
                        : "text-amber-500"
                    }
                  >
                    {b.state}
                  </span>
                  <span className="text-muted">Failures: {b.failure_count ?? 0}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Raw Diagnostic Payload */}
      <div className="border border-border rounded-xl bg-panel p-5 space-y-2">
        <div className="text-xs uppercase tracking-wider text-muted font-semibold">
          Diagnostic Telemetry Snapshot
        </div>
        <pre className="p-3 rounded-lg bg-background border border-border text-xs font-mono text-muted overflow-x-auto max-h-48">
          {JSON.stringify(readyData || liveData || { error: "Probe unreachable" }, null, 2)}
        </pre>
      </div>
    </div>
  );
}
