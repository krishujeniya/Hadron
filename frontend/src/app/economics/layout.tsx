import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Token Economics & Cost Ledger | Hadron",
  description:
    "Monitor per-review LLM token consumption, track daily budget ceilings, and audit operational spend across your engineering team.",
  alternates: {
    canonical: "/economics",
  },
  openGraph: {
    title: "Token Economics & Cost Ledger | Hadron",
    description:
      "Monitor per-review LLM token consumption, track daily budget ceilings, and audit operational spend across your engineering team.",
    url: "https://hadron.vercel.app/economics",
  },
};

export default function EconomicsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
