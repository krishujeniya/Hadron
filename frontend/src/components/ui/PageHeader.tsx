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
        "hm-page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-separator/50 min-w-0 max-w-full",
        className
      )}
    >
      <div className="min-w-0 flex-1">
        {tag && <p className="hm-page-overline text-xs font-medium text-muted mb-2">{tag}</p>}
        <h1 className="hm-page-title text-2xl sm:text-3xl font-bold tracking-tight text-foreground break-words">
          {title}
        </h1>
        {description && (
          <div className="hm-page-description mt-1.5 text-sm text-muted max-w-2xl leading-relaxed break-words">
            {description}
          </div>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5 shrink-0 min-w-0 max-w-full">
          {actions}
        </div>
      )}
    </div>
  );
}
