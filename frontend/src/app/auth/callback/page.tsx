"use client";

import { useEffect, useRef, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useGitHubAccount } from "@/features/auth/github-context";

function CallbackHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { selectAccount } = useGitHubAccount();

  const exchangeRef = useRef<Promise<import("@/lib/types").AccountProfile> | null>(null);

  const [statusText, setStatusText] = useState("Authenticating with GitHub...");
  const [errorText, setErrorText] = useState<string | null>(null);

  useEffect(() => {
    let code = searchParams.get("code");
    let state = searchParams.get("state");

    // Resilient fallback extraction for GitHub Pages SPA redirects
    if ((!code || !state) && typeof window !== "undefined") {
      try {
        const urlObj = new URL(window.location.href);
        code = code || urlObj.searchParams.get("code");
        state = state || urlObj.searchParams.get("state");

        if (!code || !state) {
          const rawSearch = window.location.search || window.location.hash;
          if (rawSearch) {
            const normalized = rawSearch.replace(/~and~/g, "&");
            const codeMatch = normalized.match(/[?&#]code=([^&#]+)/);
            const stateMatch = normalized.match(/[?&#]state=([^&#]+)/);
            if (codeMatch) code = decodeURIComponent(codeMatch[1]);
            if (stateMatch) state = decodeURIComponent(stateMatch[1]);
          }
        }
      } catch {}
    }

    if (!code || !state) {
      setErrorText("Missing GitHub authorization code or security state. Please sign in again.");
      return;
    }

    let active = true;
    // Reuse the in-flight exchange during StrictMode's effect replay.
    if (!exchangeRef.current) {
      exchangeRef.current = api.auth.callback(code!, state!);
    }
    exchangeRef.current.then((profile) => {
      if (!active) return;
      selectAccount(profile);
      setStatusText(`Authenticated as @${profile.login}. Redirecting...`);
      router.replace("/");
    }).catch((err: unknown) => {
      if (active) setErrorText(err instanceof Error ? err.message : "Authentication failed");
    });
    return () => { active = false; };
  }, [searchParams, router, selectAccount]);

  return (
    <div className="min-h-[50vh] flex items-center justify-center">
      <div className="bg-panel border border-border rounded-xl p-8 max-w-md w-full text-center space-y-4">
        {errorText ? (
          <>
            <div className="w-12 h-12 rounded-full bg-err/15 text-err flex items-center justify-center mx-auto text-xl" aria-hidden="true">
              <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-foreground">Sign-in failed</h2>
            <p className="text-sm text-err">{errorText}</p>
            <button
              onClick={() => router.push("/")}
              className="mt-4 px-4 py-2 bg-accent text-white text-xs font-medium rounded-lg hover:bg-accent/90"
            >
              Return to dashboard
            </button>
          </>
        ) : (
          <>
            <div className="w-10 h-10 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto" />
            <h2 className="text-lg font-semibold text-foreground">GitHub authentication</h2>
            <p className="text-sm text-muted">{statusText}</p>
          </>
        )}
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-muted">Processing GitHub login...</div>}>
      <CallbackHandler />
    </Suspense>
  );
}
