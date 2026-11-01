"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useGitHubAccount } from "@/lib/githubContext";
import { HadronAuthScreen } from "./HadronAuthScreen";
import { HadronLogo } from "./HadronLogo";
import { HadronIcon } from "./HadronIcon";
import { ThemeToggle } from "./ThemeToggle";
import { CommandPalette } from "./CommandPalette";
import { GitHubAccountModal } from "./GitHubAccountModal";

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

  // Allow public routes (solutions marketing pages, auth callback) to render with a dedicated public layout (T32)
  const isSolutionsRoute = pathname?.startsWith("/solutions");
  if (isSolutionsRoute) {
    return (
      <div className="min-h-screen bg-bg text-foreground flex flex-col">
        <header className="border-b border-border bg-surface px-6 py-4 flex items-center justify-between sticky top-0 z-40 backdrop-blur-md">
          <HadronLogo size="sm" animated={false} />
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/"
              className="px-3.5 py-1.5 bg-primary-action text-white hover:bg-primary-action/90 text-xs font-semibold rounded-lg transition shadow-sm"
            >
              Sign In to App →
            </Link>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none">
          {children}
        </main>
        <footer className="border-t border-separator py-6 text-center text-xs text-muted font-mono bg-panel/30">
          Hadron · Autonomous Multi-Agent PR Review Engine
        </footer>
      </div>
    );
  }

  // Allow the OAuth callback route to process even before currentAccount is stored
  if (pathname === "/auth/callback") {
    return <main className="min-h-screen bg-bg text-foreground">{children}</main>;
  }

  // If loading local state, show clean loader
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg text-foreground font-mono text-xs">
        <div className="flex flex-col items-center gap-4">
          <HadronIcon size={48} animated={true} />
          <span className="text-muted tracking-widest text-[11px]">INITIALIZING HADRON ENGINE...</span>
        </div>
      </div>
    );
  }

  // If not logged in, render the clean "Sign in with GitHub" starting screen
  if (!currentAccount) {
    return <HadronAuthScreen />;
  }

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-bg text-foreground">
      {/* Accessible Skip Link (T39 / S05) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-surface focus:text-foreground focus:border focus:border-border focus:rounded-lg focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-accent"
      >
        Skip to main content
      </a>

      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-panel sticky top-0 z-30">
        <HadronLogo size="sm" animated={false} />
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted hover:text-foreground bg-surface text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="Open command palette"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
          <ThemeToggle />
          <button
            ref={mobileTriggerRef}
            type="button"
            onClick={() => setMobileOpen(!mobileOpen)}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted hover:text-foreground bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
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
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <HadronLogo size="sm" animated={true} />
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-surface text-foreground border border-border">
              v0.1.0
            </span>
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
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-xs font-semibold text-foreground truncate">
                    @{currentAccount.login}
                  </span>
                  <span className="w-1.5 h-1.5 rounded-full bg-ok shrink-0" title="Connected" />
                </div>
                <div className="text-[10px] text-muted truncate">
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
      <main id="main-content" tabIndex={-1} className="flex-1 px-4 py-4 md:px-8 md:py-6 overflow-x-hidden min-w-0 focus:outline-none">
        {children}
      </main>

      {/* Global Command Palette */}
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />

      {/* Live Workspace Account Modal (T33) */}
      <GitHubAccountModal />
    </div>
  );
}
