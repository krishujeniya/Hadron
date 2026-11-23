"use client";

import React from "react";
import Link from "next/link";

interface HadronLogoProps {
  size?: "sm" | "md" | "lg";
  /** Retained for backwards compatibility. Brand marks do not animate. */
  animated?: boolean;
  withLink?: boolean;
  showSubtitle?: boolean;
  className?: string;
}

export function HadronLogo({
  size = "md",
  withLink = true,
  showSubtitle = false,
  className = "",
}: HadronLogoProps) {
  const dimensions = {
    sm: { size: 32, text: "text-lg", h: 32 },
    md: { size: 38, text: "text-xl", h: 38 },
    lg: { size: 48, text: "text-2xl", h: 48 },
  }[size];

  const isPages = typeof window !== "undefined" && (window.location.hostname.endsWith("github.io") || window.location.pathname.startsWith("/Hadron"));
  const basePath = isPages ? "/Hadron" : "";

  const content = (
    <span className={`inline-flex items-center gap-2.5 min-w-0 select-none ${className}`}>
      <img
        src={`${basePath}/logo.png`}
        alt="Hadron"
        width={dimensions.size}
        height={dimensions.size}
        className="shrink-0 object-contain rounded-lg"
      />
      <span className="flex flex-col leading-none">
        <span className={`font-semibold tracking-tight text-fg ${dimensions.text}`}>
          Hadron
        </span>
        {showSubtitle && (
          <span className="text-[9px] font-medium uppercase tracking-[0.1em] text-muted mt-0.5">
            Multi-agent PR review
          </span>
        )}
      </span>
    </span>
  );

  return withLink ? (
    <Link href="/" className="inline-flex items-center" title="Hadron — pull request review" aria-label="Hadron home">
      {content}
    </Link>
  ) : content;
}
