"use client";

import React from "react";

interface HadronIconProps {
  size?: number | string;
  className?: string;
  animated?: boolean;
  withPlate?: boolean;
}

export function HadronIcon({
  size = 32,
  className = "",
  animated = false,
  withPlate = true,
}: HadronIconProps) {
  return (
    <svg
      viewBox="0 0 128 128"
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="hiPlateGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#161A23" />
          <stop offset="100%" stop-color="#0B0D12" />
        </linearGradient>

        <linearGradient id="hiBeam1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#38BDF8" />
          <stop offset="50%" stopColor="#6366F1" />
          <stop offset="100%" stopColor="#A855F7" />
        </linearGradient>

        <linearGradient id="hiBeam2" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#6366F1" />
          <stop offset="50%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#10B981" />
        </linearGradient>

        <linearGradient id="hiCore" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#6366F1" stopOpacity="0.8" />
        </linearGradient>

        <filter id="hiGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Optional Rounded Container Plate */}
      {withPlate && (
        <rect
          x="4"
          y="4"
          width="120"
          height="120"
          rx="28"
          fill="url(#hiPlateGrad)"
          stroke="#1F2430"
          strokeWidth="2"
        />
      )}

      {/* Outer Collider Detector Ring with Optional Spin */}
      <circle
        cx="64"
        cy="64"
        r="50"
        fill="none"
        stroke="url(#hiBeam1)"
        strokeWidth="1.5"
        strokeDasharray="3 5"
        opacity="0.4"
        className={animated ? "animate-[spin_24s_linear_infinite] origin-center" : ""}
      />

      {/* "H" Magnetic Accelerator Pillars (Slight Inward Curve at Collision Waist) */}
      <path
        d="M 46 30 Q 50 64 46 98"
        fill="none"
        stroke="url(#hiBeam1)"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <path
        d="M 82 30 Q 78 64 82 98"
        fill="none"
        stroke="url(#hiBeam2)"
        strokeWidth="6"
        strokeLinecap="round"
      />

      {/* High-Energy Horizontal Collision Bridge */}
      <path
        d="M 48 64 L 80 64"
        fill="none"
        stroke="#FFFFFF"
        strokeWidth="4.5"
        strokeLinecap="round"
        opacity="0.95"
      />

      {/* Relativistic Crossing Beams (Rotated Particle Ellipses) */}
      <ellipse
        cx="64"
        cy="64"
        rx="42"
        ry="15"
        fill="none"
        stroke="url(#hiBeam1)"
        strokeWidth="2"
        transform="rotate(-34 64 64)"
        opacity="0.75"
        className={animated ? "animate-[pulse_3s_ease-in-out_infinite]" : ""}
      />
      <ellipse
        cx="64"
        cy="64"
        rx="42"
        ry="15"
        fill="none"
        stroke="url(#hiBeam2)"
        strokeWidth="2"
        transform="rotate(34 64 64)"
        opacity="0.75"
        className={animated ? "animate-[pulse_3s_ease-in-out_infinite_1.5s]" : ""}
      />

      {/* 4 Sub-Agent Quantum Nodes */}
      {/* 01: Security (Cyan) - Top Left */}
      <circle cx="34" cy="42" r="4.5" fill="#38BDF8" filter="url(#hiGlow)" />
      <circle cx="34" cy="42" r="1.5" fill="#FFFFFF" />

      {/* 02: Quality (Indigo) - Top Right */}
      <circle cx="94" cy="42" r="4.5" fill="#6366F1" filter="url(#hiGlow)" />
      <circle cx="94" cy="42" r="1.5" fill="#FFFFFF" />

      {/* 03: Test Coverage (Emerald) - Bottom Right */}
      <circle cx="94" cy="86" r="4.5" fill="#10B981" filter="url(#hiGlow)" />
      <circle cx="94" cy="86" r="1.5" fill="#FFFFFF" />

      {/* 04: Documentation (Violet) - Bottom Left */}
      <circle cx="34" cy="86" r="4.5" fill="#A855F7" filter="url(#hiGlow)" />
      <circle cx="34" cy="86" r="1.5" fill="#FFFFFF" />

      {/* Central Collision Flash Nucleus */}
      <circle
        cx="64"
        cy="64"
        r="8"
        fill="url(#hiCore)"
        filter="url(#hiGlow)"
        opacity="0.85"
        className={animated ? "animate-ping origin-center opacity-75" : ""}
      />
      <circle cx="64" cy="64" r="7" fill="url(#hiCore)" />
      <circle cx="64" cy="64" r="3.5" fill="#FFFFFF" />
    </svg>
  );
}
