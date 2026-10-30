"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSWRConfig } from "swr";
import { api } from "@/lib/api";
import type { DecisionAction, HITLDecisionResponse } from "@/lib/types";

const ACTIONS: { value: DecisionAction; label: string; description: string }[] = [
  { value: "approve", label: "Approve", description: "Record that you accept this review." },
  { value: "request_changes", label: "Request changes", description: "Explain what needs to change." },
  { value: "dismiss", label: "Dismiss", description: "Close this escalation without an approval." },
];
const REVIEWER_KEY = "hitl.reviewer_id";

export function HITLDecisionForm({ hitlId }: { hitlId: string }) {
  const { mutate } = useSWRConfig();
  const [action, setAction] = useState<DecisionAction | "">("");
  const [reason, setReason] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<HITLDecisionResponse | null>(null);
  const confirmation = useRef<HTMLHeadingElement>(null);
  const submitLock = useRef(false);

  useEffect(() => {
    try { setReviewerId(localStorage.getItem(REVIEWER_KEY) || ""); } catch { /* Storage is optional. */ }
  }, []);
  useEffect(() => { if (confirming) confirmation.current?.focus(); }, [confirming]);
  useEffect(() => {
    if (result || (!action && !reason)) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [action, reason, result]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!action || submitLock.current) return;
    setError(null);
    if (!reviewerId.trim() || (action === "request_changes" && !reason.trim())) {
      setError("Enter a reviewer and a reason when requesting changes.");
      return;
    }
    if (!confirming) { setConfirming(true); return; }
    submitLock.current = true;
    setSubmitting(true);
    try {
      const response = await api.hitlDecide(hitlId, { human_verdict: action, reason: reason.trim(), reviewer_id: reviewerId.trim() });
      setResult(response);
      try { localStorage.setItem(REVIEWER_KEY, reviewerId.trim()); } catch { /* Decision does not depend on storage. */ }
      void mutate((key) => typeof key === "string" && key.startsWith("/api/v1/hitl/queue"));
    } catch {
      setError("We could not confirm the decision. Your entries are preserved. Check the review status before trying again.");
    } finally { submitLock.current = false; setSubmitting(false); }
  }

  if (result) return (
    <section className="rounded-xl border border-border bg-panel p-5 space-y-3" aria-label="Decision result">
      <div role="status">
        <h3 className="font-semibold">Decision recorded</h3>
        <p className="mt-2 text-sm text-muted">{result.posted_to_github ? "Your decision was saved and posted as a review comment on GitHub." : "Your decision was saved, but it was not posted to GitHub. Contact your administrator to retry delivery."}</p>
      </div>
      <Link href="/hitl" className="inline-flex min-h-11 items-center text-sm font-medium text-accent underline underline-offset-4">Back to approvals</Link>
    </section>
  );

  return (
    <form onSubmit={onSubmit} className="rounded-xl border border-border bg-panel p-5 space-y-5">
      <fieldset disabled={confirming || submitting} className="space-y-4 disabled:opacity-70">
        <legend className="mb-3 text-sm font-semibold">Choose a decision</legend>
        <div className="space-y-2">
          {ACTIONS.map((item) => (
            <label key={item.value} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 ${action === item.value ? "border-accent bg-accent/5" : "border-border hover:bg-surface"}`}>
              <input type="radio" name="decision" value={item.value} checked={action === item.value} onChange={() => setAction(item.value)} required className="mt-1 accent-[rgb(var(--accent))]" />
              <span className="text-sm"><span className="block font-medium">{item.label}</span><span className="mt-1 block text-xs text-muted">{item.description}</span></span>
            </label>
          ))}
        </div>
        <div>
          <label htmlFor="reviewer-id" className="mb-2 block text-sm font-medium">Reviewer <span className="text-muted">(required)</span></label>
          <input id="reviewer-id" name="reviewer" autoComplete="username" spellCheck={false} value={reviewerId} onChange={(event) => setReviewerId(event.target.value)} required className="min-h-11 w-full rounded-lg border border-border bg-bg px-3 text-sm" aria-describedby="reviewer-hint" />
          <p id="reviewer-hint" className="mt-2 text-xs text-muted">GitHub handle or email. Remembered on this device.</p>
        </div>
        <div>
          <label htmlFor="decision-reason" className="mb-2 block text-sm font-medium">Reason <span className="text-muted">({action === "request_changes" ? "required" : "optional"})</span></label>
          <textarea id="decision-reason" name="reason" autoComplete="off" value={reason} onChange={(event) => setReason(event.target.value)} rows={4} required={action === "request_changes"} className="w-full rounded-lg border border-border bg-bg px-3 py-2 text-sm" aria-describedby="reason-hint" />
          <p id="reason-hint" className="mt-2 text-xs text-muted">Included in the review comment sent to GitHub.</p>
        </div>
      </fieldset>
      {confirming && (
        <div className="rounded-lg border border-warn/40 bg-warn/5 p-4 text-sm space-y-2">
          <h3 ref={confirmation} tabIndex={-1} className="font-semibold">Confirm: {ACTIONS.find((item) => item.value === action)?.label}</h3>
          <p className="text-muted">This closes the escalation in Hadron and attempts to post your decision as a GitHub review comment. You cannot edit the recorded decision here. It does not merge the pull request.</p>
        </div>
      )}
      {error && <p role="alert" className="rounded-lg border border-err/30 bg-err/5 p-3 text-sm text-err">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={submitting} className="min-h-11 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-bg disabled:opacity-60">{submitting ? "Recording decision…" : confirming ? "Confirm decision" : "Review decision"}</button>
        {confirming && <button type="button" disabled={submitting} onClick={() => { setConfirming(false); setError(null); }} className="min-h-11 rounded-lg border border-border px-4 text-sm hover:bg-surface">Edit decision</button>}
      </div>
    </form>
  );
}
