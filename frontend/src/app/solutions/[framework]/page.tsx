import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HadronLogo } from "@/components/brand/HadronLogo";

interface FrameworkSolution {
  slug: string;
  title: string;
  subtitle: string;
  badge: string;
  description: string;
  headline: string;
  targetKeywords: string[];
  features: { title: string; desc: string; agent: string }[];
  exampleDiff: {
    filename: string;
    code: string;
    finding: string;
    severity: string;
    recommendation: string;
  };
  faqs: { question: string; answer: string }[];
}

const SOLUTIONS: Record<string, FrameworkSolution> = {
  "python-security-audit": {
    slug: "python-security-audit",
    title: "Automated Python Security Audit & OWASP Code Review Bot",
    subtitle: "Eliminate SQLi, command injection, insecure deserialization, and hardcoded secrets in Python pull requests.",
    badge: "Python & Django / FastAPI Security",
    headline: "Python security checks for pull requests",
    description:
      "Hadron acts as an autonomous Python security engineer, checking pull requests against Bandit, Semgrep, and OWASP Top 10 heuristics before code merges.",
    targetKeywords: [
      "python security audit",
      "automated owasp code review",
      "python pr security bot",
      "bandit ast static analysis",
    ],
    features: [
      {
        title: "Taint Analysis for Injections",
        desc: "Tracks untrusted inputs across SQLAlchemy, raw SQL queries, and subprocess calls to prevent SQLi and RCE.",
        agent: "Security Specialist Agent",
      },
      {
        title: "Dependency CVE & Supply Chain Guard",
        desc: "Inspects poetry.lock, requirements.txt, and Pipfile changes against active CVE vulnerability registries.",
        agent: "Security Specialist Agent",
      },
      {
        title: "Cryptographic & Token Masking",
        desc: "Redacts API tokens, private keys, and passwords before diff analysis using entropy heuristics.",
        agent: "Privacy & Sanitization Agent",
      },
    ],
    exampleDiff: {
      filename: "services/auth_service.py",
      code: `- query = f"SELECT * FROM users WHERE username = '{username}'"\n+ stmt = select(User).where(User.username == username)`,
      finding: "Critical SQL Injection via f-string query formatting.",
      severity: "CRITICAL",
      recommendation: "Use parameterized SQLAlchemy statements or ORM binding instead of formatted string interpolation.",
    },
    faqs: [
      {
        question: "How does Hadron detect Python security bugs?",
        answer: "Hadron uses Tree-sitter AST parsing combined with Tiger Cloud DiskANN semantic retrieval and specialized security sub-agents to trace dangerous sinks and sources.",
      },
      {
        question: "Does Hadron support Django, Flask, and FastAPI?",
        answer: "Yes, Hadron includes dedicated static analysis rules for Django ORM queries, Flask request handlers, and FastAPI Pydantic models.",
      },
      {
        question: "Can Hadron prevent secrets and API keys from leaking into pull requests?",
        answer: "Yes. Hadron runs regex and Shannon entropy scanners on modified lines to detect hardcoded AWS tokens, GitHub PATs, private keys, and database connection strings before comments are posted.",
      },
    ],
  },
  "nextjs-pr-review": {
    slug: "nextjs-pr-review",
    title: "Next.js 14 App Router Autonomous PR Code Review Bot",
    subtitle: "Catch Server/Client Component leaks, waterfall fetches, unoptimized images, and hydration errors.",
    badge: "Next.js & React 18 Specialist",
    headline: "Full-Stack React & Next.js Performance & Architecture Audits",
    description:
      "Hadron analyzes Next.js PRs to guarantee Core Web Vitals, optimal caching strategies, and strict boundary separation between Server and Client Components.",
    targetKeywords: [
      "nextjs pr review",
      "react server components linter",
      "nextjs 14 code quality",
      "automated nextjs review bot",
    ],
    features: [
      {
        title: "Server/Client Boundary Leak Detection",
        desc: "Prevents accidental importing of server-only secrets or database clients into 'use client' components.",
        agent: "Quality Specialist Agent",
      },
      {
        title: "Suspense & Waterfall Optimization",
        desc: "Flags sequential unawaited promises in Server Components and recommends parallel Promise.all() or streaming suspense.",
        agent: "Quality Specialist Agent",
      },
      {
        title: "Image & Core Web Vitals Auditing",
        desc: "Detects unoptimized <img> tags, missing sizes, and layout shifts before deploying to production.",
        agent: "Quality Specialist Agent",
      },
    ],
    exampleDiff: {
      filename: "app/dashboard/page.tsx",
      code: `- const user = await getUser();\n- const posts = await getPosts(user.id);\n+ const [user, posts] = await Promise.all([getUser(), getPosts()]);`,
      finding: "Sequential async waterfall fetch in Server Component.",
      severity: "MEDIUM",
      recommendation: "Parallelize non-dependent async data fetches to minimize Time to First Byte (TTFB).",
    },
    faqs: [
      {
        question: "Does Hadron support Next.js App Router and Server Actions?",
        answer: "Yes, Hadron validates Server Actions for missing CSRF guards and unauthorized mutations.",
      },
      {
        question: "How does this compare to ESLint?",
        answer: "Hadron operates cross-file with codebase memory, identifying subtle architectural traps that static linters miss.",
      },
      {
        question: "How does Hadron flag React Server Component data waterfalls?",
        answer: "Hadron analyzes async Server Components for sequential await expressions where queries do not depend on preceding results, advising developers to use Promise.all() or parallel Suspense boundaries.",
      },
    ],
  },
  "fastapi-code-quality": {
    slug: "fastapi-code-quality",
    title: "FastAPI Code Quality & Async Concurrency Review Bot",
    subtitle: "Prevent blocking async event loops, Pydantic v2 deprecations, and connection pool exhaustion.",
    badge: "FastAPI & AsyncIO Performance",
    headline: "High-Throughput FastAPI Optimization On Every Commit",
    description:
      "Ensure your FastAPI microservices deliver sub-millisecond latencies by catching blocking sync I/O in async def routes and validating database pool lifecycles.",
    targetKeywords: [
      "fastapi code quality",
      "asyncio event loop blocking",
      "fastapi pr review",
      "python async best practices",
    ],
    features: [
      {
        title: "Async Event Loop Starvation Guard",
        desc: "Identifies blocking time.sleep(), synchronous requests.get(), or heavy CPU tasks executed inside async route definitions.",
        agent: "Quality Specialist Agent",
      },
      {
        title: "Pydantic v2 Migration & Validator Audit",
        desc: "Detects deprecated @validator decorators and advises modern @field_validator with model_dump() idioms.",
        agent: "Quality Specialist Agent",
      },
      {
        title: "Connection Pool Leak Detection",
        desc: "Verifies proper async context managers (async with) on SQLAlchemy sessions and Redis connections.",
        agent: "Quality Specialist Agent",
      },
    ],
    exampleDiff: {
      filename: "api/routes/data.py",
      code: `- async def get_report():\n-     time.sleep(2) # blocks loop\n+ async def get_report():\n+     await asyncio.sleep(2)`,
      finding: "Blocking sync call inside async def event loop handler.",
      severity: "HIGH",
      recommendation: "Use non-blocking asyncio.sleep or offload CPU-intensive operations to run_in_threadpool().",
    },
    faqs: [
      {
        question: "Can Hadron detect synchronous DB calls in FastAPI?",
        answer: "Yes, it detects sync session queries executed within async handlers and recommends async_sessionmaker.",
      },
      {
        question: "Does Hadron support Pydantic v1 and v2 simultaneously?",
        answer: "Yes. Hadron inspects the installed Pydantic version in project dependencies and flags deprecated v1 syntax only when upgrading to v2.",
      },
      {
        question: "How does Hadron flag blocking CPU operations?",
        answer: "Hadron parses route definition ASTs. If an async def handler contains synchronous network calls or heavy loops, it advises offloading to anyio.to_thread.run_sync or run_in_threadpool.",
      },
    ],
  },
  "go-concurrency-checker": {
    slug: "go-concurrency-checker",
    title: "Go Concurrency & Goroutine Leak Autonomous Review Bot",
    subtitle: "Identify race conditions, channel deadlocks, and context cancellation traps in Golang PRs.",
    badge: "Golang Concurrency Engine",
    headline: "Bulletproof Go Services: Detect Deadlocks and Race Conditions",
    description:
      "Hadron checks Golang pull requests for unbounded goroutines, unbuffered channel deadlocks, and missed defer cancel() invocations.",
    targetKeywords: [
      "go concurrency checker",
      "golang pr review bot",
      "goroutine leak detection",
      "golang race condition ai",
    ],
    features: [
      {
        title: "Goroutine Leak Analysis",
        desc: "Checks that spawned goroutines have definitive termination paths, select exit cases, or context cancellations.",
        agent: "Quality Specialist Agent",
      },
      {
        title: "Context Propagation Verification",
        desc: "Ensures incoming context.Context is passed through to outbound network and database calls.",
        agent: "Quality Specialist Agent",
      },
      {
        title: "Mutex Lock Ordering & Defer Inspection",
        desc: "Guarantees sync.Mutex Unlock() calls are deferred immediately after Lock() to eliminate deadlocks.",
        agent: "Quality Specialist Agent",
      },
    ],
    exampleDiff: {
      filename: "worker/pool.go",
      code: `- mu.Lock()\n- if err != nil { return err }\n- mu.Unlock()\n+ mu.Lock()\n+ defer mu.Unlock()\n+ if err != nil { return err }`,
      finding: "Potential Deadlock: Mutex left locked on early error return.",
      severity: "CRITICAL",
      recommendation: "Always use defer mu.Unlock() immediately following mu.Lock() to prevent deadlock on return.",
    },
    faqs: [
      {
        question: "Does Hadron support Go 1.21+ toolchains?",
        answer: "Yes, including modern standard library slog structured logging and generics semantics.",
      },
      {
        question: "Can Hadron detect data races without executing test binaries?",
        answer: "Hadron uses static synchronization graph analysis on git diffs to detect shared memory writes without mutex protection, complementing the Go runtime race detector (go test -race).",
      },
      {
        question: "How are unbuffered channel deadlocks caught?",
        answer: "Hadron inspects channel creation AST nodes and verifies that goroutine sends have a matching concurrent receiver or select timeout case to avoid permanent channel blocking.",
      },
    ],
  },
};

const BASE_URL = process.env.NEXT_PUBLIC_APP_URL || "https://hadron.vercel.app";

export async function generateStaticParams() {
  return Object.keys(SOLUTIONS).map((framework) => ({
    framework,
  }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ framework: string }>;
}): Promise<Metadata> {
  const { framework } = await params;
  const item = SOLUTIONS[framework];
  if (!item) {
    return {
      title: "Solutions | Hadron Autonomous PR Review",
    };
  }

  return {
    title: `${item.title} | Hadron`,
    description: item.description,
    keywords: item.targetKeywords,
    alternates: {
      canonical: `${BASE_URL}/solutions/${item.slug}`,
    },
    openGraph: {
      title: `${item.title} | Hadron`,
      description: item.description,
      url: `${BASE_URL}/solutions/${item.slug}`,
      type: "article",
    },
    twitter: {
      card: "summary_large_image",
      title: `${item.title} | Hadron`,
      description: item.description,
    },
  };
}

export default async function SolutionDetailPage({
  params,
}: {
  params: Promise<{ framework: string }>;
}) {
  const { framework } = await params;
  const solution = SOLUTIONS[framework];
  if (!solution) {
    notFound();
  }

  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "TechArticle",
        headline: solution.title,
        description: solution.description,
        url: `${BASE_URL}/solutions/${solution.slug}`,
        inLanguage: "en-US",
        author: {
          "@type": "Organization",
          name: "Hadron AI",
          url: "https://hadron.vercel.app",
        },
        publisher: {
          "@type": "Organization",
          name: "Hadron AI",
          url: "https://hadron.vercel.app",
          logo: "https://hadron.vercel.app/icon-512.png",
        },
        keywords: solution.targetKeywords.join(", "),
      },
      {
        "@type": "FAQPage",
        mainEntity: solution.faqs.map((faq) => ({
          "@type": "Question",
          name: faq.question,
          acceptedAnswer: {
            "@type": "Answer",
            text: faq.answer,
          },
        })),
      },
    ],
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-3 sm:px-6 space-y-10 sm:space-y-12 min-w-0 max-w-full">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      {/* Breadcrumb / Top Tag */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted font-mono min-w-0">
        <Link href="/" className="hover:text-foreground">Home</Link>
        <span>/</span>
        <span className="text-muted/60">Solutions</span>
        <span>/</span>
        <span className="text-foreground font-medium break-all">{solution.slug}</span>
      </div>

      {/* Hero Header */}
      <div className="space-y-4 min-w-0">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-panel text-foreground border border-border font-mono max-w-full">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent shrink-0" aria-hidden="true" />
          <span className="break-words">{solution.badge}</span>
        </div>
        <h1 className="text-2xl sm:text-3xl md:text-5xl font-semibold tracking-tight text-foreground break-words">
          {solution.title}
        </h1>
        <p className="text-base sm:text-lg md:text-xl text-muted max-w-3xl leading-relaxed break-words">
          {solution.subtitle}
        </p>
        <div className="pt-2 flex flex-wrap items-center gap-3 sm:gap-4">
          <Link
            href="/"
            className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center px-6 py-3 rounded-xl bg-primary-action hover:opacity-90 text-white dark:text-black font-semibold text-sm transition shadow-sm text-center"
          >
            Deploy Hadron on GitHub free →
          </Link>
          <Link
            href="/reviews"
            className="w-full sm:w-auto inline-flex min-h-[44px] items-center justify-center px-6 py-3 rounded-xl bg-panel hover:bg-surface border border-border text-foreground font-semibold text-sm transition text-center"
          >
            Explore live reviews
          </Link>
        </div>
      </div>

      {/* Architecture Highlights */}
      <div className="space-y-6 min-w-0">
        <h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-foreground border-b border-separator pb-3 break-words">
          Specialist agent capabilities
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 min-w-0">
          {solution.features.map((feat, idx) => (
            <div
              key={idx}
              className="p-4 sm:p-5 rounded-xl border border-border bg-surface hover:border-muted/50 transition-colors space-y-2 shadow-sm min-w-0"
            >
              <div className="text-[11px] text-accent font-medium font-semibold break-words">
                {feat.agent}
              </div>
              <h3 className="text-base font-semibold text-foreground break-words">
                {feat.title}
              </h3>
              <p className="text-xs text-muted leading-relaxed break-words">
                {feat.desc}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Real-World Diff Finding Example */}
      <div className="space-y-4 min-w-0 max-w-full">
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground border-b border-separator pb-3 font-mono break-words">
          Automated finding detection preview
        </h2>
        <div className="rounded-xl border border-border bg-surface overflow-hidden shadow-sm min-w-0 max-w-full">
          <div className="px-4 py-2 bg-panel border-b border-border flex flex-wrap items-center justify-between gap-2 text-xs font-mono min-w-0">
            <span className="text-muted break-all">{solution.exampleDiff.filename}</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-err/10 text-err border border-err/30 shrink-0">
              {solution.exampleDiff.severity}
            </span>
          </div>
          <div className="p-3.5 sm:p-4 font-mono text-xs overflow-x-auto bg-panel text-foreground min-w-0 max-w-full">
            <pre className="whitespace-pre-wrap break-all min-w-0 max-w-full">{solution.exampleDiff.code}</pre>
          </div>
          <div className="p-3.5 sm:p-4 bg-err/5 border-t border-border space-y-2 min-w-0">
            <div className="text-xs font-bold text-err flex items-center gap-1.5 break-words">
              <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
              <span>{solution.exampleDiff.finding}</span>
            </div>
            <div className="text-xs text-foreground/90 font-medium flex flex-wrap items-center gap-1.5 break-words">
              <span className="font-semibold text-accent shrink-0">Recommendation:</span>
              <span>{solution.exampleDiff.recommendation}</span>
            </div>
          </div>
        </div>
      </div>

      {/* FAQ Section */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold tracking-tight text-foreground border-b border-separator pb-3 font-mono">
          Frequently asked questions
        </h2>
        <div className="space-y-3">
          {solution.faqs.map((faq, idx) => (
            <div key={idx} className="p-4 rounded-xl border border-border bg-surface space-y-1.5 shadow-sm">
              <h3 className="text-sm font-semibold text-foreground">
                {faq.question}
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                {faq.answer}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* CTA Box */}
      <div className="rounded-2xl border border-border bg-surface p-8 text-center space-y-4 shadow-sm">
        <h2 className="text-2xl md:text-3xl font-semibold text-foreground">
          Accelerate your code reviews with Hadron
        </h2>
        <p className="text-sm text-muted max-w-xl mx-auto">
          Install the Hadron GitHub App in under 2 minutes. Free for open-source and public repositories.
        </p>
        <Link
          href="/"
          className="inline-block px-8 py-3.5 rounded-xl bg-primary-action hover:opacity-90 text-white dark:text-black font-semibold text-sm transition shadow-sm"
        >
          Get started with GitHub OAuth →
        </Link>
      </div>
    </div>
  );
}
