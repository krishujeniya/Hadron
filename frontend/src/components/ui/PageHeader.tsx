"use client";

import React from "react";
import clsx from "clsx";

export interface PageHeaderProps {
  title: string;
  description?: React.ReactNode;
  tag?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  tag,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={clsx(
        "flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-separator/50",
        className
      )}
    >
      <div>
        {tag && (
          <p className="text-xs font-mono font-medium uppercase tracking-wider text-muted mb-1">
            {tag}
          </p>
        )}
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground font-mono">
          {title}
        </h1>
        {description && (
          <div className="mt-1.5 text-sm text-muted max-w-2xl leading-relaxed">
            {description}
          </div>
        )}
      </div>
      {actions && <div className="flex items-center gap-2.5 shrink-0">{actions}</div>}
    </div>
  );
}
