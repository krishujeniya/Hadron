"use client";

import React, { useState, useEffect } from "react";
import { useGitHubAccount } from "@/lib/githubContext";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";

const PRESET_ACCOUNTS = [
  {
    login: "krishujeniya",
    name: "Krish Ujeniya",
    desc: "Project creator & maintainer",
  },
  {
    login: "octocat",
    name: "The Octocat",
    desc: "GitHub sample & fixture organization",
  },
];

export function GitHubAccountModal() {
  const { isModalOpen, closeAccountModal, currentAccount, connectAccount } = useGitHubAccount();

  const [inputAccount, setInputAccount] = useState("");
  const [inputToken, setInputToken] = useState("");
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [showOAuthHelp, setShowOAuthHelp] = useState(false);
  const [oauthAvailable, setOauthAvailable] = useState<boolean | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Check if OAuth is configured on backend
  useEffect(() => {
    async function checkOAuth() {
      try {
        const res = await fetch("/api/v1/auth/github/login");
        if (res.ok) {
          const data = await res.json();
          setOauthAvailable(!!data.oauth_available);
        }
      } catch {
        setOauthAvailable(false);
      }
    }
    if (isModalOpen) {
      checkOAuth();
    }
  }, [isModalOpen]);

  if (!isModalOpen) return null;

  const handleSelectPreset = async (login: string) => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await connectAccount(login);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to connect account");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputAccount.trim()) {
      setErrorMsg("Please enter a GitHub account username or organization");
      return;
    }
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await connectAccount(inputAccount.trim(), inputToken.trim() || undefined);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to connect account");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOAuthSignIn = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/v1/auth/github/login");
      const data = await res.json();
      if (data.oauth_available && data.authorize_url) {
        window.location.href = data.authorize_url;
      } else {
        setShowOAuthHelp(true);
        setErrorMsg("GitHub OAuth App is not configured on the server. You can enter your username directly below, or configure OAuth credentials in .env.");
      }
    } catch {
      setErrorMsg("Failed to initiate GitHub OAuth login");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
        onClick={currentAccount ? closeAccountModal : undefined}
        aria-hidden="true"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-modal-title"
        className="relative z-10 bg-surface border border-border rounded-2xl shadow-2xl max-w-lg w-full p-6 text-foreground animate-in fade-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto"
      >
        {currentAccount && (
          <button
            type="button"
            onClick={closeAccountModal}
            className="absolute top-4 right-4 text-muted hover:text-foreground text-sm p-1.5 rounded-lg hover:bg-panel transition"
            aria-label="Close modal"
          >
            ✕
          </button>
        )}

        {/* Header */}
        <div className="flex items-center gap-3 mb-5 border-b border-separator pb-4">
          <div className="w-10 h-10 rounded-xl bg-accent/10 text-accent flex items-center justify-center font-bold text-lg shrink-0 border border-accent/20">
            <svg className="w-6 h-6 fill-current" viewBox="0 0 24 24" aria-hidden="true">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
          </div>
          <div>
            <h2 id="account-modal-title" className="text-lg font-semibold text-foreground">
              Select GitHub Account
            </h2>
            <p className="text-muted text-xs">
              Choose which GitHub account or organization to inspect for PR reviews
            </p>
          </div>
        </div>

        {errorMsg && (
          <div className="mb-4">
            <Alert
              variant="error"
              title="Connection Error"
              description={errorMsg}
              onDismiss={() => setErrorMsg(null)}
            />
          </div>
        )}

        {/* OAuth Button & Status */}
        <div className="mb-5">
          <Button
            type="button"
            onClick={handleOAuthSignIn}
            isLoading={isSubmitting}
            variant="primary"
            className="w-full"
            leftIcon={
              <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
            }
          >
            <span>Sign in with GitHub</span>
            {oauthAvailable === false && (
              <span className="text-[10px] bg-warn/20 text-warn border border-warn/30 px-1.5 py-0.5 rounded font-mono ml-2">
                Setup required
              </span>
            )}
          </Button>

          {/* OAuth Setup Helper Accordion */}
          {showOAuthHelp && (
            <div className="mt-3 p-3 bg-panel border border-border rounded-lg text-xs space-y-2 text-muted">
              <div className="font-semibold text-foreground">How to enable GitHub OAuth:</div>
              <ol className="list-decimal list-inside space-y-1 text-[11px]">
                <li>Go to GitHub: <span className="font-mono text-accent">Settings &gt; Developer settings &gt; OAuth Apps</span></li>
                <li>Click <strong>New OAuth App</strong></li>
                <li>Set Authorization callback URL to: <code className="text-foreground bg-surface px-1 py-0.5 rounded border border-border">http://localhost:3000/auth/callback</code></li>
                <li>Copy <strong>Client ID</strong> &amp; <strong>Client Secret</strong> into your <code className="text-foreground bg-surface px-1 py-0.5 rounded border border-border">.env</code> file:
                  <pre className="mt-1 p-2 bg-surface border border-border rounded font-mono text-[10px] text-accent">
GITHUB_CLIENT_ID=your_id_here
GITHUB_CLIENT_SECRET=your_secret_here
                  </pre>
                </li>
              </ol>
            </div>
          )}
        </div>

        <div className="relative flex py-2 items-center mb-4">
          <div className="flex-grow border-t border-separator"></div>
          <span className="flex-shrink mx-3 text-[11px] text-accent font-semibold tracking-wider font-mono">
            INSTANT CONNECT
          </span>
          <div className="flex-grow border-t border-separator"></div>
        </div>

        {/* Quick Presets */}
        <div className="mb-5">
          <label className="text-xs text-muted block mb-2 font-medium">Click to select an account instantly:</label>
          <div className="grid grid-cols-2 gap-2.5">
            {PRESET_ACCOUNTS.map((p) => (
              <button
                key={p.login}
                type="button"
                onClick={() => handleSelectPreset(p.login)}
                disabled={isSubmitting}
                className="text-left p-3 rounded-xl border border-border bg-panel hover:border-accent hover:bg-accent/5 transition flex flex-col justify-between group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-foreground group-hover:text-accent group-hover:underline">@{p.login}</span>
                  <span className="text-[10px] text-ok font-medium">✓ instant</span>
                </div>
                <div className="text-[11px] text-muted truncate mt-1">{p.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Username Input Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="modal-username" className="text-xs text-foreground block mb-1 font-medium">Or enter any GitHub Username / Org:</label>
            <div className="relative">
              <span className="absolute left-3 top-2.5 text-muted text-sm font-mono" aria-hidden="true">@</span>
              <input
                id="modal-username"
                type="text"
                value={inputAccount}
                onChange={(e) => setInputAccount(e.target.value)}
                placeholder="e.g. krishujeniya, facebook, vercel"
                className="w-full bg-panel border border-border rounded-lg pl-7 pr-3 py-2 text-sm font-mono text-foreground placeholder:text-muted/60 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent"
              />
            </div>
          </div>

          <div>
            <button
              type="button"
              onClick={() => setShowTokenInput(!showTokenInput)}
              className="text-xs text-accent hover:underline flex items-center gap-1 font-medium"
            >
              {showTokenInput ? "− Hide" : "+ Add"} Personal Access Token (optional, for private repos)
            </button>

            {showTokenInput && (
              <div className="mt-2">
                <input
                  type="password"
                  value={inputToken}
                  onChange={(e) => setInputToken(e.target.value)}
                  placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                  className="w-full bg-panel border border-border rounded-lg px-3 py-2 text-sm font-mono text-foreground placeholder:text-muted/60 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                />
                <p className="text-[10px] text-muted mt-1">
                  Allows viewing private repos and increases GitHub API rate limits.
                </p>
              </div>
            )}
          </div>

          <div className="pt-2">
            <Button
              type="submit"
              disabled={isSubmitting || !inputAccount.trim()}
              isLoading={isSubmitting}
              variant="secondary"
              className="w-full"
            >
              Use This Account
            </Button>
          </div>
        </form>

        <div className="mt-4 text-center">
          <p className="text-[11px] text-muted">
            All reviews, webhooks, and repository views are filtered exclusively for the chosen account.
          </p>
        </div>
      </div>
    </div>
  );
}
