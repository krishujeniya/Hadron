"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { DecisionAction } from "@/lib/types";

const ACTIONS: { value: DecisionAction; label: string; key: string; tone: string }[] = [
  { value: "approve", label: "Approve", key: "A", tone: "bg-ok/20 text-ok border-ok/40" },
  {
    value: "request_changes",
    label: "Request changes",
    key: "R",
    tone: "bg-err/20 text-err border-err/40",
  },
  {
    value: "dismiss",
    label: "Dismiss",
    key: "D",
    tone: "bg-muted/20 text-muted border-muted/40",
  },
];

const REVIEWER_KEY = "hitl.reviewer_id";

export function HITLDecisionForm({ hitlId }: { hitlId: string }) {
  const router = useRouter();
  const [action, setAction] = useState<DecisionAction>("approve");
  const [reason, setReason] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Restore last-used reviewer on mount.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem(REVIEWER_KEY);
    if (saved) setReviewerId(saved);

    function handleKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        setAction("approve");
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        setAction("request_changes");
      } else if (e.key === "d" || e.key === "D") {
        e.preventDefault();
        setAction("dismiss");
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmedReviewer = reviewerId.trim();
    if (!trimmedReviewer) {
      setError("Reviewer ID is required.");
      return;
    }
    if (action === "request_changes" && !reason.trim()) {
      setError("Reason is required when requesting changes.");
      return;
    }
    setSubmitting(true);
    try {
      window.localStorage.setItem(REVIEWER_KEY, trimmedReviewer);
      await api.hitlDecide(hitlId, {
        human_verdict: action,
        reason: reason.trim(),
        reviewer_id: trimmedReviewer,
      });
      router.push("/hitl");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="border border-border rounded-lg bg-panel p-4 space-y-4"
    >
      <div>
        <label className="block text-xs uppercase tracking-wide text-muted mb-2">
          Decision
        </label>
        <div className="flex flex-wrap gap-2">
          {ACTIONS.map((a) => (
            <button
              key={a.value}
              type="button"
              onClick={() => setAction(a.value)}
              className={`px-3 py-1.5 rounded border text-sm transition inline-flex items-center gap-1.5 ${
                action === a.value
                  ? a.tone
                  : "border-border text-muted hover:text-white"
              }`}
            >
              <span>{a.label}</span>
              <kbd className="px-1 py-0.2 rounded text-[10px] font-mono bg-bg/70 border border-border/80 text-muted">
                {a.key}
              </kbd>
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-xs uppercase tracking-wide text-muted mb-2">
          Reviewer ID <span className="text-err">*</span>
        </label>
        <input
          value={reviewerId}
          onChange={(e) => setReviewerId(e.target.value)}
          placeholder="github handle or email"
          required
          className="w-full bg-bg border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-accent"
        />
        <div className="text-xs text-muted mt-1">
          Remembered locally for next time.
        </div>
      </div>

      <div>
        <label className="block text-xs uppercase tracking-wide text-muted mb-2">
          Reason {action === "request_changes" && <span className="text-err">*</span>}
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          required={action === "request_changes"}
          placeholder="Why are you making this decision? Visible on the PR."
          className="w-full bg-bg border border-border rounded px-3 py-2 text-sm focus:outline-none focus:border-accent"
        />
      </div>

      {error && (
        <div className="text-sm text-err border border-err/30 bg-err/10 rounded px-3 py-2">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="px-4 py-2 rounded bg-accent text-bg font-medium disabled:opacity-50"
      >
        {submitting ? "Submitting…" : "Submit decision"}
      </button>
    </form>
  );
}
