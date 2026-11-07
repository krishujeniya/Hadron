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
    sm: { width: 136, height: 39 },
    md: { width: 170, height: 48 },
    lg: { width: 240, height: 68 },
  }[size];

  const isPages = typeof window !== "undefined" && (window.location.hostname.endsWith("github.io") || window.location.pathname.startsWith("/Hadron"));
  const basePath = isPages ? "/Hadron" : "";

  const content = (
    <span className={`inline-flex flex-col items-start justify-center min-w-0 ${className}`}>
      <img
        src={`${basePath}/logo.svg`}
        alt="Hadron"
        width={dimensions.width}
        height={dimensions.height}
        className="block dark:hidden shrink-0"
      />
      <img
        src={`${basePath}/logo-dark.svg`}
        alt="Hadron"
        width={dimensions.width}
        height={dimensions.height}
        className="hidden dark:block shrink-0"
      />
      {showSubtitle && (
        <span className="text-[9px] font-medium uppercase tracking-[0.1em] text-muted">
          Multi-agent pull request review
        </span>
      )}
    </span>
  );

  return withLink ? (
    <Link href="/" className="inline-flex items-center" title="Hadron — pull request review" aria-label="Hadron home">
      {content}
    </Link>
  ) : content;
}
