"use client";

import React from "react";
import clsx from "clsx";

export type StatusVariant = "success" | "warning" | "error" | "neutral" | "info";

export interface StatusProps {
  variant?: StatusVariant;
  label: string;
  className?: string;
  showDot?: boolean;
}

export function Status({
  variant = "neutral",
  label,
  className,
  showDot = true,
}: StatusProps) {
  const styles: Record<StatusVariant, { badge: string; dot: string }> = {
    success: {
      badge: "border-ok/30 bg-ok/10 text-ok",
      dot: "bg-ok",
    },
    warning: {
      badge: "border-warn/30 bg-warn/10 text-warn",
      dot: "bg-warn",
    },
    error: {
      badge: "border-err/30 bg-err/10 text-err",
      dot: "bg-err",
    },
    info: {
      badge: "border-accent/30 bg-accent/10 text-accent",
      dot: "bg-accent",
    },
    neutral: {
      badge: "border-border bg-surface text-muted",
      dot: "bg-muted",
    },
  };

  const current = styles[variant] || styles.neutral;

  return (
    <span
      className={clsx(
        "inline-flex shrink-0 items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        current.badge,
        className
      )}
    >
      {showDot && (
        <span
          className={clsx("h-1.5 w-1.5 rounded-full shrink-0", current.dot)}
          aria-hidden="true"
        />
      )}
      <span>{label}</span>
    </span>
  );
}
