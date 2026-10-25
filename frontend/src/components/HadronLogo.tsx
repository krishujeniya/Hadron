"use client";

import React from "react";
import Link from "next/link";
import { HadronIcon } from "./HadronIcon";

interface HadronLogoProps {
  size?: "sm" | "md" | "lg";
  animated?: boolean;
  withLink?: boolean;
  showSubtitle?: boolean;
  className?: string;
}

export function HadronLogo({
  size = "md",
  animated = false,
  withLink = true,
  showSubtitle = true,
  className = "",
}: HadronLogoProps) {
  const iconSizes = {
    sm: 26,
    md: 32,
    lg: 48,
  };

  const titleSizes = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-2xl",
  };

  const subtitleSizes = {
    sm: "text-[9px]",
    md: "text-[10px]",
    lg: "text-xs",
  };

  const content = (
    <div className={`flex items-center gap-2.5 group select-none ${className}`}>
      <HadronIcon
        size={iconSizes[size]}
        animated={animated}
        withPlate={true}
        className="transition-transform duration-300 group-hover:scale-105"
      />
      <div className="flex flex-col">
        <div
          className={`font-mono font-extrabold tracking-wider text-white group-hover:text-accent transition duration-150 ${titleSizes[size]}`}
        >
          HADRON
        </div>
        {showSubtitle && (
          <div
            className={`text-muted font-mono tracking-tight -mt-0.5 uppercase ${subtitleSizes[size]}`}
          >
            ai pr review engine
          </div>
        )}
      </div>
    </div>
  );

  if (withLink) {
    return (
      <Link href="/" className="inline-block" title="Hadron — Autonomous AI PR Review">
        {content}
      </Link>
    );
  }

  return content;
}
