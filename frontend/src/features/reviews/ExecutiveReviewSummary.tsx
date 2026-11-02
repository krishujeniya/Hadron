import Link from "next/link";
import type { ReviewDetail } from "@/lib/types";

export function ExecutiveReviewSummary({ data }: { data: ReviewDetail }) {
  const findings = data.findings ?? [];
  const priority = findings.filter((finding) => ["critical", "high", "major"].includes(finding.severity.toLowerCase()));
  return (
    <section aria-labelledby="review-summary-heading" className="rounded-xl border border-border bg-panel p-5 sm:p-6 space-y-4">
      <div>
        <h2 id="review-summary-heading" className="font-semibold">Review summary</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
          {data.status === "failed" ? "This review did not complete. Check the recorded findings and review the pull request on GitHub." : data.status === "completed" ? `This review recorded ${findings.length} finding${findings.length === 1 ? "" : "s"}. ${priority.length > 0 ? `${priority.length} are marked high priority or critical.` : "None of the recorded findings are marked high priority or critical."}` : "This review has not completed. Findings and recommendations may change as processing continues."}
        </p>
      </div>
      {data.needs_human_review && <div className="rounded-lg border border-warn/30 bg-warn/5 p-4 text-sm"><p className="font-medium">A human review is needed</p><p className="mt-1 text-muted">{data.human_review_reason || "Assess the findings before making a decision."}</p><Link href="/hitl" className="mt-2 inline-flex min-h-11 items-center font-medium underline underline-offset-4">Open approvals</Link></div>}
      <p className="text-xs leading-relaxed text-muted">Automated findings are suggestions to assess alongside the code and tests. A recommendation to approve is not a guarantee that the change is free of defects.</p>
    </section>
  );
}
