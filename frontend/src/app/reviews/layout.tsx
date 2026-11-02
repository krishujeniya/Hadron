import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pull Request Reviews | Hadron",
  description:
    "Track autonomous code review statuses, specialist findings, and approval recommendations across your GitHub pull requests.",
  alternates: {
    canonical: "/reviews",
  },
  openGraph: {
    title: "Pull Request Reviews | Hadron",
    description:
      "Track autonomous code review statuses, specialist findings, and approval recommendations across your GitHub pull requests.",
    url: "https://hadron.vercel.app/reviews",
  },
};

export default function ReviewsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
