"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useGitHubAccount } from "@/features/auth/github-context";
import { HadronLogo } from "@/components/brand/HadronLogo";
import { HadronIcon } from "@/components/brand/HadronIcon";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { GitHubAccountModal } from "@/features/auth/GitHubAccountModal";

// Primary work navigation & secondary operations (T32)
const PRIMARY_NAV = [
  { href: "/", label: "Overview", iconId: "overview" },
  { href: "/reviews", label: "Reviews", iconId: "reviews" },
  { href: "/hitl", label: "Human Review", iconId: "hitl", badge: "Action" },
  { href: "/repositories", label: "Repositories", iconId: "repos" },
];

const SECONDARY_NAV = [
  { href: "/economics", label: "Usage and cost", iconId: "economics" },
  { href: "/health", label: "Service health", iconId: "health" },
];

function NavIcon({ id }: { id: string }) {
  if (id === "overview") {
    return (
      <svg className="w-4 h-4 shrink-0 text-muted group-hover:text-foreground transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
      </svg>
    );
  }
  if (id === "reviews") {
    return (
      <svg className="w-4 h-4 shrink-0 text-muted group-hover:text-foreground transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="18" cy="18" r="3" />
        <circle cx="6" cy="6" r="3" />
        <path d="M13 6h3a2 2 0 0 1 2 2v7" />
        <line x1="6" y1="9" x2="6" y2="21" />
      </svg>
    );
  }
  if (id === "hitl") {
    return (
      <svg className="w-4 h-4 shrink-0 text-muted group-hover:text-foreground transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    );
  }
  if (id === "repos") {
    return (
      <svg className="w-4 h-4 shrink-0 text-muted group-hover:text-foreground transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      </svg>
    );
  }
  if (id === "economics") {
    return (
      <svg className="w-4 h-4 shrink-0 text-muted group-hover:text-foreground transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <line x1="12" y1="1" x2="12" y2="23" />
        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    );
  }
  if (id === "health") {
    return (
      <svg className="w-4 h-4 shrink-0 text-muted group-hover:text-foreground transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    );
  }
  return null;
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { currentAccount, isLoading, logout, openAccountModal } = useGitHubAccount();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const mobileTriggerRef = useRef<HTMLButtonElement>(null);

  // Close mobile drawer on route navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Handle Escape key for mobile drawer
  useEffect(() => {
    if (!mobileOpen) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setMobileOpen(false);
        mobileTriggerRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [mobileOpen]);

  // Global keyboard shortcut for Command Palette (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Allow public routes (solutions marketing pages, health telemetry, auth callback, and public landing page) to render without auth blocks (T32)
  const isSolutionsRoute = pathname?.startsWith("/solutions");
  const isDocsRoute = pathname?.startsWith("/docs");
  const isPublicHome = pathname === "/" && !currentAccount;
  const isPublicHealth = pathname === "/health" && !currentAccount;

  if (isLoading && pathname !== "/auth/callback") {
    return <main className="min-h-screen bg-bg text-foreground flex items-center justify-center" aria-busy="true"><p role="status">Checking your session…</p></main>;
  }

  if (isSolutionsRoute || isDocsRoute || isPublicHome || isPublicHealth || (!currentAccount && pathname !== "/auth/callback")) {
    return (
      <div className="hadron-public min-h-screen bg-bg text-foreground flex flex-col">
        {/* Accessible Skip Link (T39 / S05) */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-surface focus:text-foreground focus:border focus:border-border focus:rounded-lg focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-accent"
        >
          Skip to main content
        </a>

        <header className="hm-header border-b border-border bg-surface/85 px-3 sm:px-6 py-3 flex items-center justify-between sticky top-0 z-40 backdrop-blur-xl min-w-0 max-w-full">
          <div className="flex items-center gap-3 sm:gap-6 min-w-0">
            <HadronLogo size="sm" animated={false} />
            <nav className="hidden md:flex items-center gap-5 text-xs font-mono text-muted" aria-label="Public sections">
              <a href="/#demo" className="hover:text-foreground transition-colors py-1">Live demo</a>
              <a href="/#how-it-works" className="hover:text-foreground transition-colors py-1">How it works</a>
              <Link href="/docs" className="hover:text-foreground transition-colors py-1">Docs</Link>
              <a href="/#security" className="hover:text-foreground transition-colors py-1">Security</a>
              <a href="/#pricing" className="hover:text-foreground transition-colors py-1">Pricing</a>
              <a href="/#faq" className="hover:text-foreground transition-colors py-1">FAQ</a>
            </nav>
          </div>
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <ThemeToggle />
            <button
              type="button"
              onClick={openAccountModal}
              aria-label="Sign In to App"
              className="inline-flex min-h-[44px] items-center px-2.5 sm:px-4 py-2 bg-primary-action text-white dark:text-black hover:opacity-90 text-xs font-semibold rounded-xl transition shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent active:scale-[0.98] shrink-0"
            >
              <span className="hidden sm:inline">Sign In to App →</span>
              <span className="sm:hidden">Sign In →</span>
            </button>
          </div>
        </header>

        <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 max-w-full overflow-x-hidden focus:outline-none">
          {isSolutionsRoute || isDocsRoute || isPublicHome || isPublicHealth ? children : (
            <section className="max-w-lg mx-auto px-6 py-20 space-y-4">
              <h1 className="text-2xl font-semibold">Sign in to your workspace</h1>
              <p className="text-muted">Authenticate with GitHub to view your reviews and repository activity.</p>
              <button type="button" onClick={openAccountModal} className="min-h-[44px] px-4 py-2 rounded-lg bg-primary-action text-white dark:text-black font-semibold hover:opacity-90 transition">Sign in with GitHub</button>
            </section>
          )}
        </main>

        <footer className="border-t border-border py-8 text-xs text-muted font-mono bg-panel/30">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <p className="font-semibold text-foreground">Hadron · Autonomous Multi-Agent PR Review Engine</p>
              <p className="text-[11px] text-muted/80 mt-1">Four specialist agents reviewing pull request diffs in parallel.</p>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-xs">
              <Link href="/solutions/python-security-audit" className="hover:text-foreground transition-colors">Python Security</Link>
              <Link href="/solutions/nextjs-pr-review" className="hover:text-foreground transition-colors">Next.js Review</Link>
              <Link href="/docs" className="hover:text-foreground transition-colors">Docs</Link>
              <a href="https://github.com/krishujeniya/Hadron" target="_blank" rel="noreferrer" className="hover:text-foreground transition-colors">GitHub ↗</a>
            </div>
          </div>
        </footer>

        {/* Mount GitHubAccountModal in public view too (T31) */}
        <GitHubAccountModal />
      </div>
    );
  }

  // Allow the OAuth callback route to process even before currentAccount is stored
  if (pathname === "/auth/callback") {
    return <main className="min-h-screen bg-bg text-foreground">{children}</main>;
  }

  // If on a private route (/reviews, /hitl, /repositories) and not logged in, render the clean auth screen

  if (!currentAccount) return null;

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-bg text-foreground">
      {/* Accessible Skip Link (T39 / S05) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-surface focus:text-foreground focus:border focus:border-border focus:rounded-lg focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-accent"
      >
        Skip to main content
      </a>

      {/* Mobile Top Bar with Ergonomic 44px Touch Targets */}
      <div className="md:hidden flex items-center justify-between px-3 py-2 border-b border-border bg-panel sticky top-0 z-30">
        <HadronLogo size="sm" animated={false} />
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="w-11 h-11 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl border border-border text-muted hover:text-foreground bg-surface text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent active:scale-[0.98] transition-transform duration-150"
            aria-label="Open command palette"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
          <div className="min-w-[44px] min-h-[44px] flex items-center justify-center">
            <ThemeToggle />
          </div>
          <button
            ref={mobileTriggerRef}
            type="button"
            onClick={() => setMobileOpen(!mobileOpen)}
            className="w-11 h-11 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl border border-border text-muted hover:text-foreground bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent active:scale-[0.98] transition-transform duration-150"
            aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileOpen}
            aria-controls="mobile-nav-drawer"
          >
            {mobileOpen ? (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/60 backdrop-blur-xs z-40 transition-opacity"
          onClick={() => {
            setMobileOpen(false);
            mobileTriggerRef.current?.focus();
          }}
          aria-hidden="true"
        />
      )}

      {/* Sidebar / Mobile Drawer (hidden on mobile when closed so offscreen links cannot be focused) */}
      <aside
        id="mobile-nav-drawer"
        aria-label="Main Navigation"
        className={clsx(
          "border-r border-border bg-panel flex flex-col justify-between shrink-0 transition-transform duration-200 z-50",
          "w-64 fixed inset-y-0 left-0 md:static md:translate-x-0",
          mobileOpen ? "translate-x-0 flex" : "-translate-x-full hidden md:flex"
        )}
      >
        <div className="flex flex-col flex-1 overflow-y-auto">
          {/* Hadron Logo & Header */}
          <div className="px-5 py-4 border-b border-border flex items-center">
            <HadronLogo size="sm" animated={true} />
          </div>

          {/* Authenticated GitHub Account Card */}
          <div className="p-3 mx-3 my-3 rounded-xl border border-border bg-surface">
            <div className="flex items-center gap-2.5">
              {currentAccount.avatar_url ? (
                <img
                  src={currentAccount.avatar_url}
                  alt={currentAccount.login}
                  width={32}
                  height={32}
                  className="w-8 h-8 rounded-full border border-border shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold text-xs shrink-0">
                  {currentAccount.login.slice(0, 2).toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="font-mono text-xs font-semibold text-foreground break-all">
                    @{currentAccount.login}
                  </span>
                  <span className="w-1.5 h-1.5 rounded-full bg-ok shrink-0" title="Connected" />
                </div>
                <div className="text-[10px] text-muted break-words">
                  {currentAccount.name || "GitHub Account"}
                </div>
              </div>
            </div>

            <div className="mt-2.5 pt-2 border-t border-separator flex items-center justify-between text-[11px]">
              <button
                type="button"
                onClick={openAccountModal}
                className="text-accent hover:underline text-[11px] font-mono"
              >
                Switch workspace
              </button>
              <button
                type="button"
                onClick={logout}
                className="text-muted hover:text-foreground text-[11px] font-mono transition"
                title="Disconnect GitHub account"
              >
                Sign out →
              </button>
            </div>
          </div>

          {/* Universal Quick Command / Search Bar */}
          <div className="px-3 mb-2">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="w-full flex items-center justify-between px-3 py-1.5 rounded-xl border border-border bg-surface hover:bg-panel transition-colors text-xs text-muted hover:text-foreground group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <span className="flex items-center gap-2">
                <svg className="w-3.5 h-3.5 text-muted group-hover:text-foreground transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <span className="group-hover:text-foreground transition-colors">Commands</span>
              </span>
              <kbd className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-panel text-muted border border-border">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* Primary Navigation links */}
          <nav aria-label="Primary" className="px-3 py-2 space-y-1">
            <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-muted font-semibold">
              Work
            </div>
            {PRIMARY_NAV.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname === item.href || pathname?.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={clsx(
                    "flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all group",
                    active
                      ? "bg-accent/10 text-accent font-semibold border-l-2 border-accent"
                      : "text-muted hover:text-foreground hover:bg-surface"
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    <NavIcon id={item.iconId} />
                    <span>{item.label}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {item.badge && !active && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase tracking-wider bg-warn/10 text-warn border border-warn/30">
                        {item.badge}
                      </span>
                    )}
                    {active && <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
                  </div>
                </Link>
              );
            })}
          </nav>

          {/* Secondary Operations links */}
          <nav aria-label="Operations" className="px-3 py-2 space-y-1 mt-2">
            <div className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider text-muted font-semibold">
              Operations
            </div>
            {SECONDARY_NAV.map((item) => {
              const active =
                pathname === item.href || pathname?.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={clsx(
                    "flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all group",
                    active
                      ? "bg-accent/10 text-accent font-semibold border-l-2 border-accent"
                      : "text-muted hover:text-foreground hover:bg-surface"
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    <NavIcon id={item.iconId} />
                    <span>{item.label}</span>
                  </div>
                  {active && <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* System Health & Theme / Footer */}
        <div className="px-4 py-3 border-t border-border flex items-center justify-between text-[10px] text-muted font-mono">
          <div className="flex items-center gap-1.5">
            <span>Hadron Engine</span>
            <span className="text-ok flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-ok" />
              live
            </span>
          </div>
          <ThemeToggle />
        </div>
      </aside>

      {/* Main Content */}
      <main id="main-content" tabIndex={-1} className="flex-1 px-3 sm:px-6 md:px-8 py-4 md:py-6 pb-24 md:pb-6 overflow-x-hidden min-w-0 max-w-full focus:outline-none">
        {children}
      </main>

      {/* Mobile Ergonomic Bottom Navigation Dock */}
      <nav
        aria-label="Mobile Bottom Navigation"
        className="md:hidden fixed bottom-0 left-0 right-0 z-30 bg-panel/90 backdrop-blur-xl border-t border-border/80 px-1.5 py-1 flex items-center justify-around safe-area-pb shadow-lg max-w-full overflow-hidden"
      >
        {PRIMARY_NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname?.startsWith(`${item.href}/`);
          return (
            <Link
              key={`mob-${item.href}`}
              href={item.href}
              className={clsx(
                "flex flex-col items-center justify-center min-w-[54px] min-h-[48px] py-1 px-2 rounded-xl text-[10px] font-mono transition-transform duration-150 active:scale-[0.98]",
                active
                  ? "text-accent font-semibold"
                  : "text-muted hover:text-foreground"
              )}
            >
              <div className="relative">
                <NavIcon id={item.iconId} />
                {item.badge && !active && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-warn" />
                )}
              </div>
              <span className="mt-1 leading-none truncate max-w-[64px]">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Global Command Palette */}
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />

      {/* Live Workspace Account Modal (T33) */}
      <GitHubAccountModal />
    </div>
  );
}
