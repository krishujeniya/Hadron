import "./globals.css";
import type { Metadata } from "next";
import { SWRProvider } from "@/lib/swr";
import { GitHubProvider } from "@/features/auth/github-context";
import { ThemeProvider } from "@/lib/themeContext";
import { Shell } from "@/components/layout/Shell";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://hadron.vercel.app"),
  title: "Hadron | AI PR Review Engine",
  description: "Ship pull requests faster with autonomous code reviews that catch critical security vulnerabilities, logic flaws, and test gaps before merge.",
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
    description: "Ship pull requests faster with autonomous code reviews that catch critical security vulnerabilities, logic flaws, and test gaps before merge.",
    url: "https://hadron.vercel.app",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Hadron PR Review Engine" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Hadron | AI PR Review Engine",
    description: "Ship pull requests faster with autonomous code reviews that catch critical security vulnerabilities, logic flaws, and test gaps before merge.",
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
        "Autonomous multi-agent pull request review engine that coordinates Security, Quality, Test, and Docs agents in parallel.",
      url: "https://hadron.vercel.app",
    },
    {
      "@type": "Organization",
      name: "Hadron AI",
      url: "https://hadron.vercel.app",
      logo: "https://hadron.vercel.app/icon-512.png",
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
