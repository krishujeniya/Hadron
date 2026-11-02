import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Human-in-the-Loop Review Queue | Hadron",
  description:
    "Triage escalated pull requests, inspect borderline agent confidence scores, and approve findings before GitHub publication.",
  alternates: {
    canonical: "/hitl",
  },
  openGraph: {
    title: "Human-in-the-Loop Review Queue | Hadron",
    description:
      "Triage escalated pull requests, inspect borderline agent confidence scores, and approve findings before GitHub publication.",
    url: "https://hadron.vercel.app/hitl",
  },
};

export default function HitlLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
