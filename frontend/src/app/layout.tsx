import "./globals.css";
import "./marketing.css";
import "./workspace.css";
import type { Metadata } from "next";
import { SWRProvider } from "@/lib/swr";
import { GitHubProvider } from "@/features/auth/github-context";
import { ThemeProvider } from "@/lib/themeContext";
import { Shell } from "@/components/layout/Shell";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://hadron.pages.dev"),
  title: "Hadron | Autonomous PR Review Engine",
  description: "Automate code reviews on GitHub pull requests. Four parallel specialist agents inspect diffs across security, code quality, test coverage, and documentation before merge.",
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/ulogo-favicon.ico" },
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/ulogo-favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/ulogo-favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/ulogo-android-chrome-192x192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { url: "/ulogo-android-chrome-512x512.png", sizes: "512x512", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
    apple: [
      { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
      { url: "/ulogo-apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
  manifest: "/site.webmanifest",
  authors: [{ name: "Krish Ujeniya", url: "https://github.com/krishujeniya" }],
  creator: "Krish Ujeniya",
  keywords: [
    "Hadron",
    "PR review",
    "code review agent",
    "AI PR review",
    "AST code analysis",
    "GitHub PR automation",
    "Krish Ujeniya",
    "Krish Ujeniya projects",
  ],
  openGraph: {
    title: "Hadron | Autonomous PR Review Engine",
    description: "Automate code reviews on GitHub pull requests. Four parallel specialist agents inspect diffs across security, code quality, test coverage, and documentation before merge.",
    url: "https://hadron.pages.dev",
    images: [{ url: "/ulogo-og-image.png", width: 1200, height: 630, alt: "Hadron multi-agent pull request review: four specialist agents, one review" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Hadron | Autonomous PR Review Engine",
    description: "Automate code reviews on GitHub pull requests. Four parallel specialist agents inspect diffs across security, code quality, test coverage, and documentation before merge.",
    creator: "@krishujeniya",
    images: ["/ulogo-og-image.png"],
  },
};

const schemaOrgData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Person",
      "@id": "https://krishujeniya.dev/#krishujeniya",
      name: "Krish Ujeniya",
      url: "https://github.com/krishujeniya",
      jobTitle: "Software Engineer & AI Systems Architect",
      sameAs: [
        "https://github.com/krishujeniya",
        "https://www.linkedin.com/in/krishujeniya",
        "https://x.com/krishujeniya",
      ],
    },
    {
      "@type": "SoftwareApplication",
      name: "Hadron",
      applicationCategory: "DeveloperApplication",
      operatingSystem: "All",
      description:
        "Autonomous multi-agent pull request review engine that coordinates Security, Quality, Test, and Documentation agents in parallel.",
      url: "https://hadron.pages.dev",
      author: { "@id": "https://krishujeniya.dev/#krishujeniya" },
      creator: { "@id": "https://krishujeniya.dev/#krishujeniya" },
    },
    {
      "@type": "Organization",
      name: "Hadron AI",
      url: "https://hadron.pages.dev",
      logo: "https://hadron.pages.dev/ulogo-icon-512.png",
      sameAs: ["https://github.com/krishujeniya/Hadron"],
    },
    {
      "@type": "WebSite",
      name: "Hadron",
      url: "https://hadron.pages.dev",
    },
    {
      "@type": "FAQPage",
      mainEntity: [
        {
          "@type": "Question",
          name: "Who built and created Hadron?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Hadron was architected and built by Krish Ujeniya (@krishujeniya), a software engineer and AI systems researcher.",
          },
        },
        {
          "@type": "Question",
          name: "How does Hadron prevent hallucinations common in AI chatbots?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Rather than asking a single general-purpose chat model to review raw files, Hadron parses the Abstract Syntax Tree, extracts modified symbols, and runs deterministic rule validators. Every reported issue requires exact file, line number, and rule citations.",
          },
        },
        {
          "@type": "Question",
          name: "Can Hadron automatically approve or block pull requests?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "Yes. Hadron can be added to your GitHub branch protection rules as a required status check. Depending on your configuration, clean reviews pass immediately, while critical security flaws request changes and block merge.",
          },
        },
        {
          "@type": "Question",
          name: "What permissions does the GitHub App require?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "The GitHub App requests read access to pull request diffs and repository metadata, and write access to pull request reviews and status checks. It does not require admin, billing, or organization-level write permissions.",
          },
        },
        {
          "@type": "Question",
          name: "How does the Human-in-the-Loop review queue work?",
          acceptedAnswer: {
            "@type": "Answer",
            text:
              "When an agent computes confidence below your configured threshold (such as 85%), or flags high-risk database migrations, the PR is routed to your Hadron HITL queue for human sign-off before comments are published to GitHub.",
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
      <body suppressHydrationWarning>
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
