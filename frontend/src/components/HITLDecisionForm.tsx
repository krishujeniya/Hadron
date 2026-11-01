"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSWRConfig } from "swr";
import { api, ApiError } from "@/lib/api";
import { useGitHubAccount } from "@/lib/githubContext";
import { Button } from "@/components/ui/Button";
import type { DecisionAction, HITLDecisionResponse } from "@/lib/types";

const ACTIONS: { value: DecisionAction; label: string; description: string }[] = [
  {
    value: "approve",
    label: "Approve Review",
    description: "Accept automated review findings and clear escalation gate.",
  },
  {
    value: "request_changes",
    label: "Request Changes",
    description: "Require author to resolve findings before pull request can proceed.",
  },
  {
    value: "dismiss",
    label: "Dismiss Escalation",
    description: "Close escalation without approval. Findings remain on record.",
  },
];

const DRAFT_KEY_PREFIX = "hitl.draft.";

interface HITLDecisionFormProps {
  hitlId: string;
  onResolved?: (res: HITLDecisionResponse) => void;
}

export function HITLDecisionForm({ hitlId, onResolved }: HITLDecisionFormProps) {
  const { mutate } = useSWRConfig();
  const { currentAccount } = useGitHubAccount();

  const [action, setAction] = useState<DecisionAction | "">("");
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflictDetail, setConflictDetail] = useState<string | null>(null);
  const [result, setResult] = useState<HITLDecisionResponse | null>(null);

  const confirmationRef = useRef<HTMLHeadingElement>(null);
  const reasonInputRef = useRef<HTMLTextAreaElement>(null);
  const submitLock = useRef(false);

  // Restore draft notes on mount if available
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`${DRAFT_KEY_PREFIX}${hitlId}`);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.action) setAction(parsed.action);
        if (parsed.reason) setReason(parsed.reason);
      }
    } catch {
      // Storage unavailable or disabled
    }
  }, [hitlId]);

  // Persist draft notes as user types
  useEffect(() => {
    if (result) return;
    try {
      if (action || reason) {
        localStorage.setItem(
          `${DRAFT_KEY_PREFIX}${hitlId}`,
          JSON.stringify({ action, reason })
        );
      }
    } catch {
      // Storage errors ignored
    }
  }, [hitlId, action, reason, result]);

  // Focus confirmation prompt when entering review stage
  useEffect(() => {
    if (confirming) {
      confirmationRef.current?.focus();
    }
  }, [confirming]);

  // Protect unsaved input from accidental tab closing
  useEffect(() => {
    if (result || (!action && !reason)) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [action, reason, result]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!action || submitLock.current || submitting) return;

    setError(null);
    setConflictDetail(null);

    // Inline field validation
    if (action === "request_changes" && !reason.trim()) {
      setError("Please provide a reason explaining what changes are required.");
      reasonInputRef.current?.focus();
      return;
    }

    if (!confirming) {
      setConfirming(true);
      return;
    }

    // Lock to prevent double-click duplicate submission
    submitLock.current = true;
    setSubmitting(true);

    try {
      const response = await api.hitlDecide(hitlId, {
        human_verdict: action,
        reason: reason.trim(),
        reviewer_id: currentAccount?.login || "session_reviewer",
      });

      setResult(response);
      onResolved?.(response);

      // Clean up saved draft upon successful submission
      try {
        localStorage.removeItem(`${DRAFT_KEY_PREFIX}${hitlId}`);
      } catch {
        // Ignored
      }

      // Revalidate queues and review details
      void mutate((key) => typeof key === "string" && key.startsWith("/api/v1/hitl/"));
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError(
            "Your session expired. Your draft notes are safely preserved. Please sign in again in another tab and retry."
          );
        } else if (err.status === 403) {
          setError(
            "Access denied: You do not have permission to submit human determinations (requires REVIEWER or ADMIN role)."
          );
        } else if (err.status === 409) {
          setConflictDetail(
            "Conflict: This review was already decided by another reviewer. Your decision was not recorded to prevent conflicting determinations."
          );
          // Refresh review detail to display updated resolution
          void mutate(`/api/v1/hitl/${encodeURIComponent(hitlId)}`);
        } else if (err.status === 422) {
          setError("Validation failed: Please ensure all required fields are filled out correctly.");
          reasonInputRef.current?.focus();
        } else {
          setError(
            `Server error (${err.status}): ${err.message}. Your entries are preserved; safe to retry.`
          );
        }
      } else {
        setError(
          "A network error occurred while recording determination. Your entries are preserved; safe to retry."
        );
      }
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  }

  // Post-submission result state
  if (result) {
    return (
      <section
        className="rounded-xl border border-ok/40 bg-panel p-5 space-y-4"
        aria-label="Decision confirmation"
      >
        <div role="status" className="space-y-2">
          <div className="flex items-center gap-2 text-ok font-semibold text-sm">
            <span>✓</span>
            <span>Human Determination Recorded</span>
          </div>
          <p className="text-xs text-muted">
            Determination: <strong className="text-foreground uppercase">{result.human_verdict}</strong>
          </p>
          <div className="rounded-lg border border-border bg-surface p-3 text-xs space-y-1">
            <p className="text-foreground">
              {result.posted_to_github ? (
                <span>
                  ✓ Determination posted as an official review on GitHub under your authenticated identity.
                </span>
              ) : (
                <span className="text-warn">
                  ⚠️ Determination is recorded in Hadron audit ledger, but publication to GitHub is queued
                  or awaiting token confirmation.
                </span>
              )}
            </p>
            <p className="text-muted text-[11px]">
              Decision ID: <span className="font-mono">{result.feedback_id || result.hitl_review_id || hitlId}</span>
            </p>
          </div>
        </div>

        <Link
          href="/hitl"
          className="inline-flex min-h-9 items-center rounded-lg border border-border bg-surface px-4 text-xs font-medium text-foreground hover:bg-raised transition-colors"
        >
          Return to Human Review Queue
        </Link>
      </section>
    );
  }

  // Conflict state
  if (conflictDetail) {
    return (
      <div role="alert" className="rounded-xl border border-warn/40 bg-warn/10 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-foreground">Determination Conflict</h3>
        <p className="text-xs text-muted leading-relaxed">{conflictDetail}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setConflictDetail(null);
            setConfirming(false);
            void mutate(`/api/v1/hitl/${encodeURIComponent(hitlId)}`);
          }}
        >
          Refresh review state
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="rounded-xl border border-border bg-panel p-5 space-y-5">
      <fieldset disabled={confirming || submitting} className="space-y-4 disabled:opacity-75">
        <legend className="text-sm font-semibold text-foreground">Select Determination</legend>

        <div className="space-y-2.5">
          {ACTIONS.map((item) => (
            <label
              key={item.value}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                action === item.value
                  ? "border-accent bg-accent/10"
                  : "border-border bg-surface hover:bg-raised"
              }`}
            >
              <input
                type="radio"
                name="decision"
                value={item.value}
                checked={action === item.value}
                onChange={() => setAction(item.value)}
                required
                className="mt-0.5 accent-[rgb(var(--accent))]"
              />
              <span className="text-xs">
                <span className="block font-semibold text-foreground">{item.label}</span>
                <span className="mt-0.5 block text-muted">{item.description}</span>
              </span>
            </label>
          ))}
        </div>

        {/* Reviewer Identity Notice */}
        <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs text-muted">
          <span>Reviewer: </span>
          <strong className="text-foreground font-mono">
            {currentAccount?.login ? `@${currentAccount.login}` : "Authenticated Session"}
          </strong>{" "}
          <span className="text-[11px] block mt-0.5">
            Decisions are permanently attributed to your server-authenticated credentials in the audit ledger.
          </span>
        </div>

        {/* Reason / Rationale textarea */}
        <div className="space-y-1.5">
          <label
            htmlFor="decision-reason"
            className="block text-xs font-medium text-foreground tracking-wide"
          >
            Reviewer rationale{" "}
            <span className="text-muted font-normal">
              ({action === "request_changes" ? "Required" : "Optional"})
            </span>
          </label>
          <textarea
            ref={reasonInputRef}
            id="decision-reason"
            name="reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder={
              action === "request_changes"
                ? "Describe specific security, architectural, or testing issues that must be addressed…"
                : "Add optional reviewer context for the PR author and audit log…"
            }
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-xs text-foreground placeholder:text-muted/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
        </div>
      </fieldset>

      {/* Confirmation Step */}
      {confirming && (
        <div
          role="region"
          aria-label="Confirm decision"
          className="rounded-lg border border-warn/40 bg-warn/10 p-4 space-y-2 text-xs"
        >
          <h3
            ref={confirmationRef}
            tabIndex={-1}
            className="font-semibold text-foreground focus-visible:outline-none"
          >
            Confirm: {ACTIONS.find((item) => item.value === action)?.label}
          </h3>
          <p className="text-muted leading-relaxed">
            This records a binding determination in Hadron and triggers publication to GitHub. You cannot
            edit or undo the decision once submitted. Submitting this determination does not merge the
            pull request.
          </p>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div role="alert" className="rounded-lg border border-err/40 bg-err/10 p-3 text-xs text-err">
          {error}
        </div>
      )}

      {/* Form Buttons */}
      <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border">
        <Button
          type="submit"
          disabled={submitting}
          size="sm"
          className="min-h-9"
        >
          {submitting
            ? "Recording determination…"
            : confirming
            ? "Confirm determination"
            : "Review determination"}
        </Button>

        {confirming && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={submitting}
            onClick={() => {
              setConfirming(false);
              setError(null);
            }}
          >
            Edit entries
          </Button>
        )}
      </div>
    </form>
  );
}
