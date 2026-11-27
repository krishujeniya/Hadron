"use client";

import React from "react";

export interface HadronIconProps {
  size?: number | string;
  className?: string;
  /** Kept for compatibility: the new identity is intentionally static. */
  animated?: boolean;
  /** Kept for compatibility: the four-agent mark never needs a container plate. */
  withPlate?: boolean;
}

/**
 * Canonical 4-agent identity: the shared central diamond represents the
 * consolidated review; the four arms are distinguished by shades of the
 * current text color (black/white monochrome palette only).
 * SVG remains crisp on high-density displays and uses no filters or orbit rings.
 */
export function HadronIcon({ size = 32, className = "" }: HadronIconProps) {
  return (
    <svg
      viewBox="0 0 256 256"
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
      aria-hidden="true"
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
        <path d="M88 63 128 105 168 63" strokeOpacity="0.95" strokeWidth="31" />
        <path d="M193 88 151 128 193 168" strokeOpacity="0.72" strokeWidth="31" />
        <path d="M168 193 128 151 88 193" strokeOpacity="0.5" strokeWidth="31" />
        <path d="M63 168 105 128 63 88" strokeOpacity="0.32" strokeWidth="31" />
      </g>
      <circle cx="128" cy="24" r="17" fill="currentColor" fillOpacity="0.95" />
      <circle cx="232" cy="128" r="17" fill="currentColor" fillOpacity="0.72" />
      <circle cx="128" cy="232" r="17" fill="currentColor" fillOpacity="0.5" />
      <circle cx="24" cy="128" r="17" fill="currentColor" fillOpacity="0.32" />
      <rect x="112" y="112" width="32" height="32" rx="4" transform="rotate(45 128 128)" fill="currentColor" fillOpacity="0.9" />
    </svg>
  );
}
