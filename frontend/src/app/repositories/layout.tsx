import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Connected Repositories | Hadron",
  description:
    "Manage connected GitHub repositories, configure webhook triggers, and monitor active branch protection review policies.",
  alternates: {
    canonical: "/repositories",
  },
  openGraph: {
    title: "Connected Repositories | Hadron",
    description:
      "Manage connected GitHub repositories, configure webhook triggers, and monitor active branch protection review policies.",
    url: "https://hadron.vercel.app/repositories",
  },
};

export default function RepositoriesLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
