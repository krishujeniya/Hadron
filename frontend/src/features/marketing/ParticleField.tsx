"use client";

import { useEffect, useRef, useState } from "react";

type Formation = "drift" | "orbit";
type Particle = {
  x: number; y: number; vx: number; vy: number; baseX: number; baseY: number;
  size: number; depth: number; rotation: number; spin: number;
  shape: number; color: string; opacity: number; phase: number;
};

const PALETTE = ["#4285F4", "#EA4335", "#FBBC04", "#34A853", "#F5F7FB", "#B9C4D3"];
const TWO_PI = Math.PI * 2;
const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v));

function seed(index: number, salt: number) {
  const value = Math.sin(index * 127.1 + salt * 311.7) * 43758.5453;
  return value - Math.floor(value);
}

/**
 * Decorative and fully optional Canvas 2D layer.
 * All meaningful information is ordinary HTML above the canvas.
 * Physics is timestep-normalized, intersection-paused and reduced-motion aware.
 */
export function ParticleField() {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointerRef = useRef({ x: -1000, y: -1000, active: false });
  const formationRef = useRef<Formation>("drift");
  const [formation, setFormation] = useState<Formation>("drift");

  formationRef.current = formation;

  useEffect(() => {
    const host = hostRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d", { alpha: true });
    if (!host || !canvas || !ctx) return;

    const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const coarseQuery = window.matchMedia("(pointer: coarse)");
    const saveData = Boolean((navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData);
    let reduced = reducedQuery.matches || saveData;
    let visible = true;
    let width = 0;
    let height = 0;
    let last = 0;
    let frame = 0;
    let particles: Particle[] = [];
    let disposed = false;

    function newParticles() {
      const count = reduced ? 34 : coarseQuery.matches ? 42 : 84;
      particles = Array.from({ length: count }, (_, i) => ({
        x: seed(i, 1) * width,
        y: seed(i, 2) * height,
        vx: (seed(i, 3) - 0.5) * 0.38,
        vy: (seed(i, 4) - 0.5) * 0.25,
        baseX: seed(i, 1) * width,
        baseY: seed(i, 2) * height,
        size: 2 + seed(i, 5) * 7,
        depth: 0.4 + seed(i, 6) * 0.8,
        rotation: seed(i, 7) * TWO_PI,
        spin: (seed(i, 8) - 0.5) * 0.011,
        shape: i % 5,
        color: PALETTE[i % PALETTE.length],
        opacity: 0.2 + seed(i, 9) * 0.6,
        phase: seed(i, 10) * TWO_PI,
      }));
    }

    function resize() {
      if (disposed || !canvas || !host || !ctx) return;
      const bounds = host.getBoundingClientRect();
      width = Math.max(1, bounds.width);
      height = Math.max(1, bounds.height);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      newParticles();
      if (reduced) render(0);
    }

    function render(now: number) {
      if (!ctx) return;
      ctx.clearRect(0, 0, width, height);
      const dt = last ? clamp((now - last) / 16.667, 0.3, 2) : 1;
      last = now;
      const orbit = formationRef.current === "orbit";
      const time = now * 0.00025;
      const cx = width * 0.52;
      const cy = height * 0.52;
      const orbitRadius = Math.min(width, height) * 0.35;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        if (!reduced) {
          if (orbit) {
            const angle = (i / particles.length) * TWO_PI + time * (0.25 + p.depth * 0.15);
            const radius = orbitRadius * (0.58 + 0.46 * seed(i, 11));
            const tx = cx + Math.cos(angle) * radius;
            const ty = cy + Math.sin(angle) * radius * 0.88;
            p.vx = (p.vx + (tx - p.x) * 0.006 * dt) * Math.pow(0.88, dt);
            p.vy = (p.vy + (ty - p.y) * 0.006 * dt) * Math.pow(0.88, dt);
          } else {
            p.vx += Math.sin(time * 3 + p.phase) * 0.004 * dt;
            p.vy -= 0.005 * dt;
            p.vx *= Math.pow(0.994, dt);
            p.vy *= Math.pow(0.994, dt);
          }
          const pointer = pointerRef.current;
          if (pointer.active) {
            const dx = p.x - pointer.x;
            const dy = p.y - pointer.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            const radius = Math.min(140, Math.max(90, width * 0.23));
            if (distance > 0.1 && distance < radius) {
              const push = Math.pow(1 - distance / radius, 2) * 0.18 * dt;
              p.vx += (dx / distance) * push;
              p.vy += (dy / distance) * push;
            }
          }
          p.vx = clamp(p.vx, -2.2, 2.2);
          p.vy = clamp(p.vy, -2.2, 2.2);
          p.x += p.vx * dt;
          p.y += p.vy * dt;
          p.rotation += p.spin * dt;
          if (!orbit) {
            const margin = 24;
            if (p.y < -margin) p.y = height + margin;
            if (p.y > height + margin) p.y = -margin;
            if (p.x < -margin) p.x = width + margin;
            if (p.x > width + margin) p.x = -margin;
          }
        } else if (orbit) {
          const angle = (i / particles.length) * TWO_PI;
          p.x = cx + Math.cos(angle) * orbitRadius * (0.58 + 0.46 * seed(i, 11));
          p.y = cy + Math.sin(angle) * orbitRadius * 0.8;
        } else {
          p.x = p.baseX;
          p.y = p.baseY;
        }

        const size = p.size * p.depth;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rotation);
        ctx.globalAlpha = p.opacity;
        ctx.fillStyle = p.color;
        if (p.shape === 0 || p.shape === 4) {
          ctx.beginPath();
          ctx.arc(0, 0, p.shape === 4 ? Math.max(1, size * 0.3) : size, 0, TWO_PI);
          ctx.fill();
        } else if (p.shape === 1) {
          ctx.fillRect(-size, -size, size * 2, size * 2);
        } else if (p.shape === 2) {
          ctx.beginPath();
          ctx.moveTo(0, -size);
          ctx.lineTo(size, size);
          ctx.lineTo(-size, size);
          ctx.closePath();
          ctx.fill();
        } else {
          ctx.beginPath();
          ctx.roundRect(-size * 1.35, -size * 0.4, size * 2.7, size * 0.8, size * 0.4);
          ctx.fill();
        }
        ctx.restore();
      }
    }

    function tick(now: number) {
      if (disposed || reduced || !visible || document.hidden) { frame = 0; return; }
      render(now);
      frame = requestAnimationFrame(tick);
    }

    function schedule() {
      if (!disposed && !reduced && visible && !document.hidden && !frame) {
        last = 0;
        frame = requestAnimationFrame(tick);
      }
    }

    function onVisibilityChange() {
      if (document.hidden && frame) { cancelAnimationFrame(frame); frame = 0; }
      else schedule();
    }

    function onMotionChange() {
      reduced = reducedQuery.matches || saveData;
      if (frame) { cancelAnimationFrame(frame); frame = 0; }
      resize();
      schedule();
    }

    const observer = new IntersectionObserver((entries) => {
      visible = Boolean(entries[0]?.isIntersecting);
      if (!visible && frame) { cancelAnimationFrame(frame); frame = 0; }
      else schedule();
    }, { threshold: 0.03 });
    const resizeObserver = new ResizeObserver(resize);
    observer.observe(host);
    resizeObserver.observe(host);
    document.addEventListener("visibilitychange", onVisibilityChange);
    reducedQuery.addEventListener("change", onMotionChange);
    resize();
    schedule();

    return () => {
      disposed = true;
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
      resizeObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      reducedQuery.removeEventListener("change", onMotionChange);
    };
  }, []);

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    pointerRef.current = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
      active: event.pointerType !== "touch",
    };
  }

  return (
    <div
      className="hm-field"
      ref={hostRef}
      onPointerMove={handlePointerMove}
      onPointerLeave={() => { pointerRef.current.active = false; }}
    >
      <canvas ref={canvasRef} aria-hidden="true" />
      <div className="hm-field-orbit" aria-hidden="true" />
      <div className="hm-field-controls" role="group" aria-label="Particle formation">
        <button type="button" aria-pressed={formation === "drift"} onClick={() => setFormation("drift")}>Free drift</button>
        <button type="button" aria-pressed={formation === "orbit"} onClick={() => setFormation("orbit")}>Orbit</button>
      </div>
    </div>
  );
}
