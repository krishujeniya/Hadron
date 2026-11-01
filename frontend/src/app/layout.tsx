import "./globals.css";
import type { Metadata } from "next";
import { SWRProvider } from "@/lib/swr";
import { GitHubProvider } from "@/lib/githubContext";
import { ThemeProvider } from "@/lib/themeContext";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://hadron.dev"),
  title: "Hadron | AI PR Review Engine",
  description: "Autonomous multi-agent pull request review engine",
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
    ],
    shortcut: "/favicon.svg",
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  openGraph: {
    title: "Hadron | AI PR Review Engine",
    description: "Autonomous multi-agent pull request reviews powered by LangGraph & Tiger Cloud",
    url: "https://hadron.dev",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Hadron PR Review Engine" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Hadron | AI PR Review Engine",
    description: "Autonomous multi-agent pull request reviews powered by LangGraph & Tiger Cloud",
    images: ["/og-image.png"],
  },
};

const schemaOrgData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      name: "Hadron",
      applicationCategory: "DeveloperApplication",
      operatingSystem: "All",
      description:
        "Multi-agent pull request review engine combining LangGraph orchestration, Tiger Cloud telemetry, and semantic code retrieval.",
      url: "https://hadron.dev",
    },
    {
      "@type": "Organization",
      name: "Hadron AI",
      url: "https://hadron.dev",
      logo: "https://hadron.dev/icon-512.png",
    },
    {
      "@type": "FAQPage",
      mainEntity: [
        {
          "@type": "Question",
          name: "What is Hadron AI PR Review Engine?",
          acceptedAnswer: {
            "@type": "Answer",
            "text":
              "Hadron is an autonomous multi-agent pull request review engine that coordinates Security, Quality, Test, and Docs agents in parallel with calibrated confidence scoring and human-in-the-loop escalation.",
          },
        },
        {
          "@type": "Question",
          name: "How does Hadron coordinate multiple specialist agents?",
          acceptedAnswer: {
            "@type": "Answer",
            "text":
              "Hadron uses LangGraph to fan out review tasks across specialist models with per-agent timeouts and combines findings via Bayesian confidence-weighted voting with human-in-the-loop escalation.",
          },
        },
      ],
    },
  ],
};

const themeInitScript = `
(function() {
  try {
    var stored = localStorage.getItem('hadron_theme');
    var isDark = stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches) || (stored === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
      root.classList.remove('light');
      root.style.colorScheme = 'dark';
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
      root.style.colorScheme = 'light';
    }
  } catch (e) {
    document.documentElement.classList.add('dark');
  }
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaOrgData) }}
        />
      </head>
      <body>
        <ThemeProvider>
          <GitHubProvider>
            <SWRProvider>
              <Shell>{children}</Shell>
            </SWRProvider>
          </GitHubProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
