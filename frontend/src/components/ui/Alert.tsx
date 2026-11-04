"use client";

import React from "react";
import clsx from "clsx";

export type AlertVariant = "info" | "warning" | "error" | "success";

export interface AlertProps {
  variant?: AlertVariant;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export function Alert({
  variant = "info",
  title,
  description,
  action,
  onDismiss,
  className,
}: AlertProps) {
  const styles: Record<AlertVariant, { container: string; icon: string; title: string }> = {
    info: {
      container: "border-accent/30 bg-accent/5 text-foreground",
      icon: "text-accent",
      title: "text-foreground",
    },
    warning: {
      container: "border-warn/30 bg-warn/5 text-foreground",
      icon: "text-warn",
      title: "text-foreground",
    },
    error: {
      container: "border-err/30 bg-err/5 text-foreground",
      icon: "text-err",
      title: "text-foreground",
    },
    success: {
      container: "border-ok/30 bg-ok/5 text-foreground",
      icon: "text-ok",
      title: "text-foreground",
    },
  };

  const current = styles[variant];

  return (
    <div
      role="alert"
      className={clsx(
        "flex items-start gap-3 rounded-xl border p-4 text-sm transition-all",
        current.container,
        className
      )}
    >
      <div className={clsx("mt-0.5 shrink-0", current.icon)} aria-hidden="true">
        {variant === "error" && (
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
        {variant === "warning" && (
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        )}
        {variant === "success" && (
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
        {variant === "info" && (
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <h4 className={clsx("font-semibold text-sm leading-tight break-words", current.title)}>{title}</h4>
        {description && <div className="mt-1 text-xs text-muted leading-relaxed break-words">{description}</div>}
        {action && <div className="mt-3">{action}</div>}
      </div>

      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="text-muted hover:text-foreground -mr-1 -mt-1 p-1 rounded-md transition-colors"
          aria-label="Dismiss alert"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}
