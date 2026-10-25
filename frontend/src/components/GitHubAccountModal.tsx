"use client";

import React, { useState, useEffect } from "react";
import { useGitHubAccount } from "@/lib/githubContext";

const PRESET_ACCOUNTS = [
  {
    login: "ayush488-glitch",
    name: "Ayush Singh",
    desc: "Project creator & test demo repo owner",
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
    } catch (err: any) {
      setErrorMsg("Failed to initiate GitHub OAuth login");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-panel border border-border rounded-xl shadow-2xl max-w-lg w-full p-6 text-white relative animate-in fade-in zoom-in-95 duration-200">
        {currentAccount && (
          <button
            onClick={closeAccountModal}
            className="absolute top-4 right-4 text-muted hover:text-white text-sm px-2 py-1 rounded"
          >
            ✕
          </button>
        )}

        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold text-lg shrink-0">
            <svg className="w-6 h-6 fill-current" viewBox="0 0 24 24">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
          </div>
          <div>
            <h2 className="text-xl font-semibold">Select GitHub Account</h2>
            <p className="text-muted text-xs">
              Choose which GitHub account or organization to inspect for PR reviews
            </p>
          </div>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 bg-err/15 border border-err/30 rounded text-err text-xs space-y-1">
            <div className="font-semibold">{errorMsg}</div>
          </div>
        )}

        {/* OAuth Button & Status */}
        <div className="mb-4">
          <button
            type="button"
            onClick={handleOAuthSignIn}
            disabled={isSubmitting}
            className="w-full flex items-center justify-center gap-2 bg-white text-black hover:bg-gray-200 transition font-medium text-sm py-2.5 px-4 rounded-lg shadow disabled:opacity-60"
          >
            <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
            <span>Sign in with GitHub</span>
            {oauthAvailable === false && (
              <span className="text-[10px] bg-warn/20 text-warn border border-warn/30 px-1.5 py-0.5 rounded font-mono">
                Setup required
              </span>
            )}
          </button>

          {/* OAuth Setup Helper Accordion */}
          {showOAuthHelp && (
            <div className="mt-3 p-3 bg-bg border border-border rounded-lg text-xs space-y-2 text-muted">
              <div className="font-semibold text-white">How to enable GitHub OAuth:</div>
              <ol className="list-decimal list-inside space-y-1 text-[11px]">
                <li>Go to GitHub: <span className="font-mono text-accent">Settings &gt; Developer settings &gt; OAuth Apps</span></li>
                <li>Click <strong>New OAuth App</strong></li>
                <li>Set Authorization callback URL to: <code className="text-white bg-panel px-1 py-0.5 rounded">http://localhost:3000/auth/callback</code></li>
                <li>Copy <strong>Client ID</strong> &amp; <strong>Client Secret</strong> into your <code className="text-white bg-panel px-1 py-0.5 rounded">.env</code> file:
                  <pre className="mt-1 p-2 bg-panel rounded font-mono text-[10px] text-accent">
GITHUB_CLIENT_ID=your_id_here
GITHUB_CLIENT_SECRET=your_secret_here
                  </pre>
                </li>
              </ol>
            </div>
          )}
        </div>

        <div className="relative flex py-2 items-center mb-4">
          <div className="flex-grow border-t border-border"></div>
          <span className="flex-shrink mx-3 text-[11px] text-accent font-semibold tracking-wider">
            RECOMMENDED: INSTANT CONNECT
          </span>
          <div className="flex-grow border-t border-border"></div>
        </div>

        {/* Quick Presets */}
        <div className="mb-4">
          <label className="text-xs text-muted block mb-2 font-medium">Click to select an account instantly:</label>
          <div className="grid grid-cols-2 gap-2">
            {PRESET_ACCOUNTS.map((p) => (
              <button
                key={p.login}
                type="button"
                onClick={() => handleSelectPreset(p.login)}
                disabled={isSubmitting}
                className="text-left p-3 rounded-lg border border-border bg-bg hover:border-accent hover:bg-accent/10 transition flex flex-col justify-between group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-accent group-hover:underline">@{p.login}</span>
                  <span className="text-[10px] text-ok">✓ instant</span>
                </div>
                <div className="text-[11px] text-muted truncate mt-1">{p.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Username Input Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs text-muted block mb-1 font-medium">Or enter any GitHub Username / Org:</label>
            <div className="relative">
              <span className="absolute left-3 top-2.5 text-muted text-sm font-mono">@</span>
              <input
                type="text"
                value={inputAccount}
                onChange={(e) => setInputAccount(e.target.value)}
                placeholder="e.g. ayush488-glitch, facebook, vercel"
                className="w-full bg-bg border border-border rounded-lg pl-7 pr-3 py-2 text-sm font-mono text-white placeholder-muted/60 focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          <div>
            <button
              type="button"
              onClick={() => setShowTokenInput(!showTokenInput)}
              className="text-xs text-accent hover:underline flex items-center gap-1"
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
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono text-white placeholder-muted/60 focus:outline-none focus:border-accent"
                />
                <p className="text-[10px] text-muted mt-1">
                  Allows viewing private repos and increases GitHub API rate limits.
                </p>
              </div>
            )}
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isSubmitting || !inputAccount.trim()}
              className="w-full bg-accent hover:bg-accent/90 text-white font-medium text-sm py-2.5 px-4 rounded-lg transition disabled:opacity-50"
            >
              {isSubmitting ? "Connecting..." : "Use This Account"}
            </button>
          </div>
        </form>

        <div className="mt-4 text-center">
          <p className="text-[11px] text-muted">
            All reviews, webhooks, and repository views will be filtered exclusively for the chosen account.
          </p>
        </div>
      </div>
    </div>
  );
}
