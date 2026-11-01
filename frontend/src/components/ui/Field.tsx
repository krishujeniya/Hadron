"use client";

import React, { forwardRef, useId } from "react";
import clsx from "clsx";

export interface FieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  required?: boolean;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, error, helperText, required, id, className, ...props },
  ref
) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const errorId = `${inputId}-error`;
  const helperId = `${inputId}-helper`;

  const describedBy = [error ? errorId : null, helperText ? helperId : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="w-full space-y-1.5 text-left">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-xs font-medium text-foreground tracking-wide"
        >
          {label}
          {required && <span className="ml-1 text-err" aria-hidden="true">*</span>}
        </label>
      )}
      <div className="relative">
        <input
          ref={ref}
          id={inputId}
          aria-invalid={!!error}
          aria-describedby={describedBy || undefined}
          required={required}
          className={clsx(
            "w-full rounded-lg border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            error
              ? "border-err text-err focus-visible:ring-err"
              : "border-border hover:border-muted/50 focus-visible:border-accent",
            className
          )}
          {...props}
        />
      </div>
      {error && (
        <p id={errorId} role="alert" className="text-xs text-err font-medium mt-1">
          {error}
        </p>
      )}
      {!error && helperText && (
        <p id={helperId} className="text-xs text-muted mt-1">
          {helperText}
        </p>
      )}
    </div>
  );
});
