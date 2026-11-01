"use client";

import React, { useState } from "react";
import { useGitHubAccount } from "@/lib/githubContext";
import { HadronIcon } from "./HadronIcon";
import { ThemeToggle } from "./ThemeToggle";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";

export function HadronAuthScreen() {
  const { connectAccount } = useGitHubAccount();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showTokenFallback, setShowTokenFallback] = useState(false);
  const [inputToken, setInputToken] = useState("");
  const [inputAccount, setInputAccount] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleGitHubOAuth = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/v1/auth/github/login");
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`Authentication service unavailable (${res.status}): ${text || "Please try again later"}`);
      }
      const contentType = res.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        throw new Error("Invalid response received from authentication server.");
      }
      const data = await res.json();
      if (data.oauth_available && data.authorize_url) {
        window.location.href = data.authorize_url;
      } else {
        setErrorMsg("GitHub OAuth credentials not found. Please verify GITHUB_CLIENT_ID in your server configuration.");
        setIsSubmitting(false);
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to initiate GitHub login");
      setIsSubmitting(false);
    }
  };

  const handleTokenSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputAccount.trim()) {
      setErrorMsg("Please enter a GitHub account username");
      return;
    }
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await connectAccount(inputAccount.trim(), inputToken.trim() || undefined);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to connect account");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center p-6 bg-bg text-foreground relative overflow-hidden">
      {/* Top right theme toggle */}
      <div className="absolute top-4 right-4 z-20">
        <ThemeToggle />
      </div>

      <div className="relative z-10 max-w-md w-full text-center">
        {/* Brand Icon */}
        <div className="inline-flex items-center justify-center mb-6 shadow-2xl group transition duration-300">
          <HadronIcon size={84} animated={true} withPlate={true} className="group-hover:scale-105 transition-transform duration-300" />
        </div>

        {/* Brand Name & Tagline */}
        <h1 className="text-4xl font-extrabold tracking-tight font-mono mb-2 text-foreground">
          HADRON
        </h1>
        <p className="text-muted text-xs font-mono font-medium uppercase tracking-widest mb-4">
          Autonomous AI PR Review Engine
        </p>
        <p className="text-muted text-sm leading-relaxed mb-8 px-4">
          Four specialist sub-agents review pull requests in parallel to detect vulnerabilities, enforce code quality, and verify test coverage before merge.
        </p>

        {/* Main Card */}
        <div className="bg-surface border border-border rounded-2xl p-7 shadow-2xl">
          {errorMsg && (
            <div className="mb-5 text-left">
              <Alert
                variant="error"
                title="Authentication Error"
                description={errorMsg}
                onDismiss={() => setErrorMsg(null)}
              />
            </div>
          )}

          {/* Primary CTA: Sign in with GitHub */}
          <Button
            onClick={handleGitHubOAuth}
            isLoading={isSubmitting}
            variant="primary"
            size="lg"
            className="w-full gap-3 shadow-md"
            leftIcon={
              <svg className="w-5 h-5 fill-current shrink-0" viewBox="0 0 24 24" aria-hidden="true">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
            }
            rightIcon={<span className="text-muted group-hover:translate-x-0.5 transition-transform" aria-hidden="true">→</span>}
          >
            {isSubmitting ? "Connecting to GitHub..." : "Sign in with GitHub"}
          </Button>

          {/* Quick preset for development / demo */}
          <div className="mt-5 pt-4 border-t border-separator">
            <div className="text-[11px] text-muted mb-2">Or inspect demo account:</div>
            <button
              type="button"
              onClick={() => connectAccount("krishujeniya")}
              disabled={isSubmitting}
              className="w-full py-2 px-3 rounded-lg border border-border bg-panel hover:bg-surface text-xs font-mono text-muted hover:text-foreground transition flex items-center justify-between"
            >
              <span>@krishujeniya (Hadron Live)</span>
              <span className="text-accent text-[10px]" aria-hidden="true">Open →</span>
            </button>
          </div>

          {/* Optional manual PAT toggle */}
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setShowTokenFallback(!showTokenFallback)}
              className="text-[11px] text-muted hover:text-foreground underline underline-offset-4 transition"
            >
              {showTokenFallback ? "Hide manual connection" : "Using Personal Access Token or handle?"}
            </button>

            {showTokenFallback && (
              <form onSubmit={handleTokenSubmit} className="mt-3 text-left space-y-3 pt-3 border-t border-separator">
                <div>
                  <label htmlFor="auth-username" className="text-[11px] text-muted block mb-1">GitHub Username</label>
                  <input
                    id="auth-username"
                    type="text"
                    value={inputAccount}
                    onChange={(e) => setInputAccount(e.target.value)}
                    placeholder="e.g. octocat"
                    className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-xs font-mono text-foreground placeholder:text-muted/50 focus:outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label htmlFor="auth-token" className="text-[11px] text-muted block mb-1">Personal Access Token (optional)</label>
                  <input
                    id="auth-token"
                    type="password"
                    value={inputToken}
                    onChange={(e) => setInputToken(e.target.value)}
                    placeholder="ghp_xxxxxxxxxxxx"
                    className="w-full bg-surface border border-border rounded-lg px-3 py-1.5 text-xs font-mono text-foreground placeholder:text-muted/50 focus:outline-none focus:border-accent"
                  />
                </div>
                <Button
                  type="submit"
                  disabled={isSubmitting || !inputAccount.trim()}
                  variant="secondary"
                  size="sm"
                  className="w-full"
                >
                  Connect with Handle
                </Button>
              </form>
            )}
          </div>
        </div>

        {/* Feature Grid */}
        <div className="mt-8 grid grid-cols-2 gap-3 text-left">
          <div className="p-3 rounded-xl border border-border bg-panel">
            <div className="text-foreground text-xs font-semibold font-mono">01 · SECURITY</div>
            <div className="text-muted text-[11px] mt-0.5">AST injection, secrets &amp; CWE scanning</div>
          </div>
          <div className="p-3 rounded-xl border border-border bg-panel">
            <div className="text-foreground text-xs font-semibold font-mono">02 · QUALITY</div>
            <div className="text-muted text-[11px] mt-0.5">Cyclomatic complexity &amp; code smells</div>
          </div>
          <div className="p-3 rounded-xl border border-border bg-panel">
            <div className="text-foreground text-xs font-semibold font-mono">03 · TESTS</div>
            <div className="text-muted text-[11px] mt-0.5">Coverage gap &amp; edge case verification</div>
          </div>
          <div className="p-3 rounded-xl border border-border bg-panel">
            <div className="text-foreground text-xs font-semibold font-mono">04 · HITL GATE</div>
            <div className="text-muted text-[11px] mt-0.5">Human review queue for low confidence</div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-[11px] text-muted font-mono">
          Hadron · Powered by Tiger Cloud, LangGraph &amp; pgvectorscale
        </div>
      </div>
    </div>
  );
}
