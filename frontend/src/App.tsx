import React, { Suspense, lazy } from "react";
import { ThemeProvider } from "@/lib/themeContext";
import { SWRProvider } from "@/lib/swr";
import { GitHubProvider } from "@/features/auth/github-context";
import { Shell } from "@/components/layout/Shell";
import { RouterProvider, useRouterContext } from "@/compat/next/router-context";

// Lazy load pages for efficient code splitting
const DashboardPage = lazy(() => import("@/app/page"));
const ReviewsPage = lazy(() => import("@/app/reviews/page"));
const ReviewDetailPage = lazy(() => import("@/app/reviews/[id]/page"));
const HITLQueuePage = lazy(() => import("@/app/hitl/page"));
const HITLDetailPage = lazy(() => import("@/app/hitl/[id]/page"));
const RepositoriesPage = lazy(() => import("@/app/repositories/page"));
const EconomicsPage = lazy(() => import("@/app/economics/page"));
const HealthPage = lazy(() => import("@/app/health/page"));
const DocsPage = lazy(() => import("@/app/docs/page"));
const SolutionPage = lazy(() => import("@/app/solutions/[framework]/page"));
const AuthCallbackPage = lazy(() => import("@/app/auth/callback/page"));
const NotFoundPage = lazy(() => import("@/app/not-found"));

function PageRouter() {
  const { pathname, params } = useRouterContext();

  let PageComponent = <NotFoundPage />;

  if (pathname === "/" || pathname === "") {
    PageComponent = <DashboardPage />;
  } else if (pathname === "/reviews") {
    PageComponent = <ReviewsPage />;
  } else if (pathname.startsWith("/reviews/")) {
    PageComponent = <ReviewDetailPage />;
  } else if (pathname === "/hitl") {
    PageComponent = <HITLQueuePage />;
  } else if (pathname.startsWith("/hitl/")) {
    PageComponent = <HITLDetailPage />;
  } else if (pathname === "/repositories") {
    PageComponent = <RepositoriesPage />;
  } else if (pathname === "/economics") {
    PageComponent = <EconomicsPage />;
  } else if (pathname === "/health") {
    PageComponent = <HealthPage />;
  } else if (pathname === "/docs" || pathname.startsWith("/docs/")) {
    PageComponent = <DocsPage />;
  } else if (pathname.startsWith("/solutions/")) {
    const framework = params.framework || pathname.split("/solutions/")[1] || "python-security-audit";
    // FrameworkSolutionPage accepts params
    PageComponent = <SolutionPage params={Promise.resolve({ framework })} />;
  } else if (
    pathname === "/auth/callback" ||
    pathname.startsWith("/auth/callback") ||
    pathname.includes("auth/callback") ||
    pathname.includes("auth%2Fcallback")
  ) {
    PageComponent = <AuthCallbackPage />;
  }

  return (
    <Suspense
      fallback={
        <div className="min-h-[50vh] flex items-center justify-center font-mono text-xs text-muted" aria-busy="true">
          Loading...
        </div>
      }
    >
      {PageComponent}
    </Suspense>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <SWRProvider>
        <GitHubProvider>
          <RouterProvider>
            <Shell>
              <PageRouter />
            </Shell>
          </RouterProvider>
        </GitHubProvider>
      </SWRProvider>
    </ThemeProvider>
  );
}

export default App;
