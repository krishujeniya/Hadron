import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "System Health & Telemetry | Hadron",
  description:
    "Real-time health status, circuit breaker states, and uptime metrics for the Hadron multi-agent review infrastructure.",
  alternates: {
    canonical: "/health",
  },
  openGraph: {
    title: "System Health & Telemetry | Hadron",
    description:
      "Real-time health status, circuit breaker states, and uptime metrics for the Hadron multi-agent review infrastructure.",
    url: "https://hadron.vercel.app/health",
  },
};

export default function HealthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
