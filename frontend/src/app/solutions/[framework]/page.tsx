import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HadronLogo } from "@/components/HadronLogo";

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
    headline: "Zero-Latency Python AST & Taint Analysis on Every GitHub PR",
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
        answer: "Yes, Hadron includes tailored heuristics for Django ORM, Flask request handlers, and FastAPI Pydantic request models.",
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
    ],
  },
};

export async function generateStaticParams() {
  return Object.keys(SOLUTIONS).map((framework) => ({
    framework,
  }));
}

export async function generateMetadata({
  params,
}: {
  params: { framework: string };
}): Promise<Metadata> {
  const item = SOLUTIONS[params.framework];
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
      canonical: `https://hadron.dev/solutions/${item.slug}`,
    },
    openGraph: {
      title: `${item.title} | Hadron`,
      description: item.description,
      url: `https://hadron.dev/solutions/${item.slug}`,
      type: "website",
    },
  };
}

export default function SolutionDetailPage({
  params,
}: {
  params: { framework: string };
}) {
  const solution = SOLUTIONS[params.framework];
  if (!solution) {
    notFound();
  }

  return (
    <div className="max-w-5xl mx-auto py-8 space-y-12">
      {/* Breadcrumb / Top Tag */}
      <div className="flex items-center gap-2 text-xs text-muted font-mono">
        <Link href="/" className="hover:text-foreground">Home</Link>
        <span>/</span>
        <span className="text-muted/60">Solutions</span>
        <span>/</span>
        <span className="text-accent">{solution.slug}</span>
      </div>

      {/* Hero Header */}
      <div className="space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-accent/15 text-accent border border-accent/30 font-mono">
          <span>⚡ {solution.badge}</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight text-foreground">
          {solution.title}
        </h1>
        <p className="text-lg md:text-xl text-muted max-w-3xl leading-relaxed">
          {solution.subtitle}
        </p>
        <div className="pt-2 flex flex-wrap items-center gap-4">
          <Link
            href="/"
            className="px-6 py-3 rounded-xl bg-accent hover:bg-accent/90 text-white font-semibold text-sm transition shadow-lg shadow-accent/20"
          >
            Deploy Hadron on GitHub Free →
          </Link>
          <Link
            href="/reviews"
            className="px-6 py-3 rounded-xl bg-panel hover:bg-surface border border-border text-foreground font-semibold text-sm transition"
          >
            Explore Live Reviews
          </Link>
        </div>
      </div>

      {/* Architecture Highlights */}
      <div className="space-y-6">
        <h2 className="text-2xl font-bold tracking-tight text-foreground border-b border-border pb-3">
          Specialist Agent Capabilities
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {solution.features.map((feat, idx) => (
            <div
              key={idx}
              className="p-5 rounded-xl border border-border bg-panel hover:border-accent/40 transition-colors space-y-2"
            >
              <div className="text-[11px] font-mono text-accent uppercase tracking-wider font-semibold">
                {feat.agent}
              </div>
              <h3 className="text-base font-semibold text-foreground">
                {feat.title}
              </h3>
              <p className="text-xs text-muted leading-relaxed">
                {feat.desc}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Real-World Diff Finding Example */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold tracking-tight text-foreground border-b border-border pb-3">
          Automated Finding Detection Preview
        </h2>
        <div className="rounded-xl border border-border bg-panel overflow-hidden">
          <div className="px-4 py-2 bg-surface/60 border-b border-border flex items-center justify-between text-xs font-mono">
            <span className="text-muted">{solution.exampleDiff.filename}</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-err/20 text-err border border-err/30">
              {solution.exampleDiff.severity}
            </span>
          </div>
          <div className="p-4 font-mono text-xs overflow-x-auto bg-[#07090D] text-muted">
            <pre className="whitespace-pre-wrap">{solution.exampleDiff.code}</pre>
          </div>
          <div className="p-4 bg-err/10 border-t border-border space-y-1">
            <div className="text-xs font-bold text-err">
              ⚠️ {solution.exampleDiff.finding}
            </div>
            <div className="text-xs text-foreground/90 font-medium">
              💡 Recommendation: {solution.exampleDiff.recommendation}
            </div>
          </div>
        </div>
      </div>

      {/* FAQ Section */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold tracking-tight text-foreground border-b border-border pb-3">
          Frequently Asked Questions
        </h2>
        <div className="space-y-3">
          {solution.faqs.map((faq, idx) => (
            <div key={idx} className="p-4 rounded-xl border border-border bg-panel space-y-1.5">
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
      <div className="rounded-2xl border border-accent/30 bg-gradient-to-r from-accent/10 via-panel to-panel p-8 text-center space-y-4">
        <h2 className="text-2xl md:text-3xl font-bold text-foreground">
          Accelerate Your Code Reviews With Hadron Today
        </h2>
        <p className="text-sm text-muted max-w-xl mx-auto">
          Install the Hadron GitHub App in under 2 minutes. Free for open-source and public repositories.
        </p>
        <Link
          href="/"
          className="inline-block px-8 py-3.5 rounded-xl bg-accent hover:bg-accent/90 text-white font-semibold text-sm transition shadow-lg shadow-accent/20"
        >
          Get Started with GitHub OAuth →
        </Link>
      </div>
    </div>
  );
}
