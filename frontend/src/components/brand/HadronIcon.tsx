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
 * consolidated review; the four colors represent independent specialist roles.
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
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        <path d="M88 63 128 105 168 63" stroke="#0B69F7" strokeWidth="31" />
        <path d="M193 88 151 128 193 168" stroke="#EF4050" strokeWidth="31" />
        <path d="M168 193 128 151 88 193" stroke="#08B773" strokeWidth="31" />
        <path d="M63 168 105 128 63 88" stroke="#F5B800" strokeWidth="31" />
      </g>
      <circle cx="128" cy="24" r="17" fill="#0B69F7" />
      <circle cx="232" cy="128" r="17" fill="#EF4050" />
      <circle cx="128" cy="232" r="17" fill="#08B773" />
      <circle cx="24" cy="128" r="17" fill="#F5B800" />
      <rect x="112" y="112" width="32" height="32" rx="4" transform="rotate(45 128 128)" fill="#20262F" />
    </svg>
  );
}
