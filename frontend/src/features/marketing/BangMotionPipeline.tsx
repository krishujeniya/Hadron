"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import gsap from "gsap";

interface AgentTelemetry {
  id: string;
  name: string;
  domain: string;
  status: "idle" | "scanning" | "passed" | "flagged";
  checkedCount: number;
  metric: string;
}

const INITIAL_AGENTS: AgentTelemetry[] = [
  { id: "sec", name: "Security agent", domain: "Secrets, injections, tainted sinks", status: "scanning", checkedCount: 142, metric: "0 leaks" },
  { id: "qual", name: "Quality agent", domain: "Complexity, dead code, style", status: "passed", checkedCount: 384, metric: "A+ grade" },
  { id: "arch", name: "Architecture agent", domain: "Layer boundaries, contracts", status: "scanning", checkedCount: 89, metric: "0 cycle" },
  { id: "test", name: "Test agent", domain: "Assertion density, regressions", status: "passed", checkedCount: 64, metric: "98% cov" },
];

const KINETIC_PHRASES = [
  { lead: "Four specialist agents", highlight: "inspect every diff", tail: "in parallel" },
  { lead: "Deterministic reviews replace", highlight: "manual PR bottlenecks", tail: "before merge" },
  { lead: "Verifiable telemetry proves", highlight: "zero unreviewed code", tail: "reaches main" },
];

export function BangMotionPipeline() {
  const containerRef = useRef<HTMLDivElement>(null);
  const headlineRef = useRef<HTMLDivElement>(null);
  const highlightBoxRef = useRef<HTMLSpanElement>(null);
  const laserBeamRef = useRef<HTMLDivElement>(null);
  const packetRef = useRef<SVGCircleElement>(null);

  const [phraseIndex, setPhraseIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [activeStep, setActiveStep] = useState<0 | 1 | 2 | 3>(1);
  const [agents, setAgents] = useState<AgentTelemetry[]>(INITIAL_AGENTS);
  const [reducedMotion, setReducedMotion] = useState(false);

  // Check user preference for reduced motion
  useEffect(() => {
    if (typeof window === "undefined") return;
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(media.matches);
    const listener = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, []);

  // Cycle through kinetic headlines with bang-motion timing
  const advancePhrase = useCallback(() => {
    setPhraseIndex((prev) => (prev + 1) % KINETIC_PHRASES.length);
  }, []);

  // Main GSAP animation lifecycle
  useEffect(() => {
    if (reducedMotion || !isPlaying) return;

    const ctx = gsap.context(() => {
      // 1. Kinetic headline entrance with directional blur & punchy power4 ease
      const phraseTl = gsap.timeline({
        repeat: -1,
        repeatDelay: 2.4,
        onRepeat: advancePhrase,
      });

      phraseTl
        .fromTo(
          headlineRef.current,
          { opacity: 0, y: 18, filter: "blur(6px)" },
          { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.7, ease: "power4.out" }
        )
        .fromTo(
          highlightBoxRef.current,
          { scaleX: 0, transformOrigin: "0% 50%" },
          { scaleX: 1, duration: 0.45, ease: "power3.out" },
          "-=0.3"
        )
        .to(headlineRef.current, {
          opacity: 0,
          y: -14,
          filter: "blur(4px)",
          duration: 0.4,
          ease: "power2.in",
          delay: 2.2,
        });

      // 2. Laser scan sweep across the diff inspection bay
      if (laserBeamRef.current) {
        gsap.fromTo(
          laserBeamRef.current,
          { xPercent: -100, opacity: 0 },
          {
            xPercent: 400,
            opacity: 1,
            duration: 2.8,
            repeat: -1,
            ease: "sine.inOut",
            repeatDelay: 0.6,
          }
        );
      }

      // 3. Flowing data packet along the central pipeline
      if (packetRef.current) {
        gsap.to(packetRef.current, {
          strokeDashoffset: -200,
          duration: 3,
          repeat: -1,
          ease: "none",
        });
      }
    }, containerRef);

    return () => ctx.revert();
  }, [reducedMotion, isPlaying, advancePhrase]);

  // Periodic pipeline telemetry simulation to show real activity
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setActiveStep((prev) => ((prev + 1) % 4) as 0 | 1 | 2 | 3);
      setAgents((prev) =>
        prev.map((agent) => ({
          ...agent,
          checkedCount: agent.checkedCount + Math.floor(Math.random() * 3) + 1,
          status: Math.random() > 0.85 ? "scanning" : "passed",
        }))
      );
    }, 3200);
    return () => clearInterval(interval);
  }, [isPlaying]);

  const currentPhrase = KINETIC_PHRASES[phraseIndex];

  return (
    <div
      ref={containerRef}
      className="relative overflow-hidden rounded-2xl border border-border/80 bg-gradient-to-b from-panel/90 via-surface to-surface p-4 sm:p-6 shadow-md"
      aria-label="Cinematic multi-agent PR review pipeline visualizer"
    >
      {/* Background Ambient Depth Grid & Camera Horizon */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.04] bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:16px_16px]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute top-0 left-1/4 right-1/4 h-24 bg-accent/10 blur-3xl rounded-full"
        aria-hidden="true"
      />

      {/* Top Telemetry Header & Playback Controls */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 border-b border-separator/60 pb-3.5">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span
              className={`absolute inline-flex h-full w-full rounded-full ${
                isPlaying ? "animate-ping bg-ok/75" : "bg-muted"
              }`}
            />
            <span
              className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
                isPlaying ? "bg-ok" : "bg-muted"
              }`}
            />
          </span>
          <span className="font-mono text-xs font-semibold tracking-wider uppercase text-foreground">
            Pipeline telemetry
          </span>
          <span className="hidden sm:inline-block font-mono text-[11px] text-muted border-l border-separator pl-2.5">
            4 specialist agents active
          </span>
        </div>

        {/* Playback & Inspection Buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-surface hover:bg-panel border border-border text-foreground transition-colors"
            title={isPlaying ? "Pause cinematic animation" : "Resume animation"}
            aria-label={isPlaying ? "Pause pipeline animation" : "Play pipeline animation"}
          >
            <span>{isPlaying ? "Pause" : "Play"}</span>
          </button>
          <div className="hidden xs:flex items-center gap-1 text-[11px] font-mono text-muted bg-surface/70 px-2 py-1 rounded border border-border">
            <span>Flow:</span>
            <span className="font-semibold text-accent">
              {activeStep === 0 && "Diff ingest"}
              {activeStep === 1 && "Agent fan-out"}
              {activeStep === 2 && "Synthesizing"}
              {activeStep === 3 && "Verdict published"}
            </span>
          </div>
        </div>
      </div>

      {/* Kinetic Typography Stage — Bang Motion Rule: Punchy, sentence-case, no fluff */}
      <div className="relative z-10 my-4 sm:my-6 min-h-[52px] sm:min-h-[64px] flex items-center">
        <div ref={headlineRef} className="w-full">
          <h2 className="text-base sm:text-xl md:text-2xl font-bold tracking-tight text-foreground font-mono leading-tight">
            <span>{currentPhrase.lead} </span>
            <span className="relative inline-block px-1.5 py-0.5 text-accent mx-0.5">
              <span
                ref={highlightBoxRef}
                className="absolute inset-0 rounded bg-accent/15 border border-accent/40 -z-0"
              />
              <span className="relative z-10">{currentPhrase.highlight}</span>
            </span>
            <span> {currentPhrase.tail}</span>
          </h2>
        </div>
      </div>

      {/* Multi-Agent Architectural Bay — Mobile First Grid */}
      <div className="relative z-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {agents.map((agent, idx) => {
          const isCurrentActive = activeStep === 1 || activeStep === 2;
          return (
            <div
              key={agent.id}
              className={`relative overflow-hidden rounded-xl border p-3.5 transition-all ${
                isCurrentActive && agent.status === "scanning"
                  ? "border-accent/60 bg-panel/80 shadow-sm"
                  : "border-border/70 bg-surface/80"
              }`}
            >
              {/* Subtle top indicator bar */}
              <div
                className={`absolute top-0 left-0 right-0 h-0.5 ${
                  agent.status === "passed"
                    ? "bg-ok"
                    : agent.status === "scanning"
                    ? "bg-accent animate-pulse"
                    : "bg-warn"
                }`}
              />

              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-xs font-bold text-foreground">
                      0{idx + 1}
                    </span>
                    <h3 className="font-mono text-xs font-semibold text-foreground truncate">
                      {agent.name}
                    </h3>
                  </div>
                  <p className="text-[11px] text-muted line-clamp-1 mt-0.5">
                    {agent.domain}
                  </p>
                </div>

                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded border shrink-0 ${
                    agent.status === "passed"
                      ? "bg-ok/10 text-ok border-ok/30"
                      : "bg-accent/10 text-accent border-accent/30"
                  }`}
                >
                  {agent.status}
                </span>
              </div>

              {/* Real-time telemetry metrics */}
              <div className="mt-3 flex items-center justify-between border-t border-separator/40 pt-2 text-xs font-mono">
                <span className="text-muted text-[11px]">
                  Checked: <strong className="text-foreground">{agent.checkedCount}</strong>
                </span>
                <span className="text-[11px] font-medium text-accent">
                  {agent.metric}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Laser Scanning Beam — Visual feedback of continuous code inspection */}
      <div className="relative mt-4 h-1 w-full overflow-hidden rounded-full bg-separator/50">
        <div
          ref={laserBeamRef}
          className="h-full w-24 rounded-full bg-gradient-to-r from-transparent via-accent to-transparent"
        />
      </div>

      {/* Pipeline Status Summary Bar */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-muted">
        <div className="flex items-center gap-2">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-ok" />
          <span>PostgreSQL ledger synced</span>
          <span className="text-separator">•</span>
          <span>Redis cache live</span>
        </div>
        <div className="text-right">
          <span>Target latency: &lt; 3.5s per commit</span>
        </div>
      </div>
    </div>
  );
}
