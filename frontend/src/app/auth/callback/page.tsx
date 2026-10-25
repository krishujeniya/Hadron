"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useGitHubAccount } from "@/lib/githubContext";

function CallbackHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { selectAccount } = useGitHubAccount();

  const [statusText, setStatusText] = useState("Authenticating with GitHub...");
  const [errorText, setErrorText] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (!code) {
      setErrorText("No authorization code received from GitHub.");
      return;
    }

    async function exchangeCode() {
      try {
        const res = await fetch("/api/v1/auth/github/callback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, state }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Failed to exchange code for GitHub token");
        }

        const profile = await res.json();
        selectAccount(profile);
        setStatusText(`Authenticated as @${profile.login}! Redirecting...`);
        setTimeout(() => {
          router.push("/");
        }, 800);
      } catch (err: any) {
        setErrorText(err.message || "Authentication failed");
      }
    }

    exchangeCode();
  }, [searchParams, router, selectAccount]);

  return (
    <div className="min-h-[50vh] flex items-center justify-center">
      <div className="bg-panel border border-border rounded-xl p-8 max-w-md w-full text-center space-y-4">
        {errorText ? (
          <>
            <div className="w-12 h-12 rounded-full bg-err/15 text-err flex items-center justify-center mx-auto text-xl">
              ✕
            </div>
            <h2 className="text-lg font-semibold text-white">Sign-in Failed</h2>
            <p className="text-sm text-err">{errorText}</p>
            <button
              onClick={() => router.push("/")}
              className="mt-4 px-4 py-2 bg-accent text-white text-xs font-medium rounded-lg hover:bg-accent/90"
            >
              Return to Dashboard
            </button>
          </>
        ) : (
          <>
            <div className="w-10 h-10 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto" />
            <h2 className="text-lg font-semibold text-white">GitHub Authentication</h2>
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
