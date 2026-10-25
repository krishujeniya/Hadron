"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useGitHubAccount } from "@/lib/githubContext";
import { HadronAuthScreen } from "./HadronAuthScreen";
import { HadronLogo } from "./HadronLogo";
import { HadronIcon } from "./HadronIcon";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/repositories", label: "Repositories", icon: "📂" },
  { href: "/reviews", label: "Reviews", icon: "📋" },
  { href: "/hitl", label: "Approvals", icon: "⚡", badge: "Action" },
  { href: "/economics", label: "Economics", icon: "💰" },
  { href: "/health", label: "Engine Health", icon: "🟢" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { currentAccount, isLoading, logout } = useGitHubAccount();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile drawer on route navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

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
      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-panel sticky top-0 z-30">
        <HadronLogo size="sm" animated={false} />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-border text-muted hover:text-foreground bg-bg"
            aria-label="Toggle Navigation Menu"
          >
            {mobileOpen ? "✕" : "☰"}
          </button>
        </div>
      </div>

      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/60 backdrop-blur-xs z-40 transition-opacity"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar / Mobile Drawer */}
      <aside
        className={clsx(
          "border-r border-border bg-panel flex flex-col justify-between shrink-0 transition-transform duration-200 z-50",
          "w-64 fixed inset-y-0 left-0 md:static md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        <div>
          {/* Hadron Logo & Header */}
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <HadronLogo size="sm" animated={true} />
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-white/10 text-white border border-white/20">
              v0.1.0
            </span>
          </div>

          {/* Authenticated GitHub Account Card */}
          <div className="p-3 mx-3 my-3 rounded-xl border border-border/70 bg-gradient-to-b from-panel to-bg/80">
            <div className="flex items-center gap-2.5">
              {currentAccount.avatar_url ? (
                <img
                  src={currentAccount.avatar_url}
                  alt={currentAccount.login}
                  className="w-8 h-8 rounded-full border border-border shrink-0"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-white/10 text-white flex items-center justify-center font-bold text-xs shrink-0">
                  {currentAccount.login.slice(0, 2).toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-xs font-semibold text-foreground truncate">
                    @{currentAccount.login}
                  </span>
                  <span className="w-1.5 h-1.5 rounded-full bg-white/90 animate-pulse shrink-0" title="Connected" />
                </div>
                <div className="text-[10px] text-muted truncate">
                  {currentAccount.name || "GitHub Account"}
                </div>
              </div>
            </div>

            <div className="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[11px]">
              <span className="text-muted font-mono text-[10px]">
                {currentAccount.public_repos} repos
              </span>
              <button
                onClick={logout}
                className="text-muted hover:text-white text-[11px] font-mono transition"
                title="Disconnect GitHub account"
              >
                Sign out →
              </button>
            </div>
          </div>

          {/* Nav links */}
          <nav className="px-3 py-2 space-y-1">
            {NAV.map((item) => {
              const active =
                pathname === item.href ||
                (item.href !== "/" && pathname?.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    "flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all group",
                    active
                      ? "bg-gradient-to-r from-white/15 via-white/5 to-transparent text-white font-semibold border-l-2 border-white shadow-xs"
                      : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-sm opacity-90 group-hover:scale-110 transition-transform">{item.icon}</span>
                    <span>{item.label}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {item.badge && !active && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase tracking-wider bg-white/10 text-zinc-300 border border-white/10">
                        {item.badge}
                      </span>
                    )}
                    {active && <span className="w-1.5 h-1.5 rounded-full bg-white shadow-xs shadow-white" />}
                  </div>
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
      <main className="flex-1 px-4 py-4 md:px-8 md:py-6 overflow-x-hidden min-w-0">{children}</main>
    </div>
  );
}
