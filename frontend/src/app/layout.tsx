import "./globals.css";
import type { Metadata } from "next";
import { SWRProvider } from "@/lib/swr";
import { GitHubProvider } from "@/features/auth/github-context";
import { ThemeProvider } from "@/lib/themeContext";
import { Shell } from "@/components/layout/Shell";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://hadron.vercel.app"),
  title: "Hadron | Autonomous PR Review Engine",
  description: "Automate code reviews on GitHub pull requests. Four parallel specialist agents inspect diffs across security, code quality, test coverage, and documentation before merge.",
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
    title: "Hadron | Autonomous PR Review Engine",
    description: "Automate code reviews on GitHub pull requests. Four parallel specialist agents inspect diffs across security, code quality, test coverage, and documentation before merge.",
    url: "https://hadron.vercel.app",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: "Hadron Autonomous PR Review Engine" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Hadron | Autonomous PR Review Engine",
    description: "Automate code reviews on GitHub pull requests. Four parallel specialist agents inspect diffs across security, code quality, test coverage, and documentation before merge.",
    images: ["/twitter-image"],
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
        "Autonomous multi-agent pull request review engine that coordinates Security, Quality, Test, and Documentation agents in parallel.",
      url: "https://hadron.vercel.app",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
      },
    },
    {
      "@type": "Organization",
      name: "Hadron AI",
      url: "https://hadron.vercel.app",
      logo: "https://hadron.vercel.app/icon-512.png",
      sameAs: ["https://github.com/krishujeniya/Hadron"],
    },
    {
      "@type": "WebSite",
      name: "Hadron",
      url: "https://hadron.vercel.app",
    },
    {
      "@type": "FAQPage",
      mainEntity: [
        {
          "@type": "Question",
          name: "What is Hadron PR Review Engine?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Hadron is an autonomous pull request review engine that coordinates Security, Quality, Test, and Documentation agents in parallel with calibrated confidence scoring and human-in-the-loop escalation.",
          },
        },
        {
          "@type": "Question",
          name: "How does Hadron coordinate multiple specialist agents?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Hadron uses LangGraph state machines to fan out review tasks across specialist models with per-agent timeouts and combines findings via Bayesian confidence-weighted voting with human-in-the-loop escalation.",
          },
        },
        {
          "@type": "Question",
          name: "Does Hadron store or train on customer source code?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "No. Source code is processed ephemerally in memory-isolated sandboxes with network egress blocked. Code is never used to train public or proprietary machine learning models.",
          },
        },
        {
          "@type": "Question",
          name: "Can Hadron block pull requests with critical vulnerabilities?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Yes. Hadron integrates with GitHub branch protection as a required status check. Critical security issues or regressions request changes and block merge.",
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
