"use client";

import React, { useCallback, useState } from "react";
import { useGitHubAccount } from "@/features/auth/github-context";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { api } from "@/lib/api";

export function GitHubAccountModal() {
  const { isModalOpen, closeAccountModal, connectAccount } = useGitHubAccount();
  const [inputAccount, setInputAccount] = useState("");
  const [inputToken, setInputToken] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleOAuthSignIn = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const isPages = typeof window !== "undefined" && (window.location.hostname.endsWith("github.io") || window.location.pathname.startsWith("/Hadron"));
      const basePath = isPages ? "/Hadron" : "";
      const redirect = `${window.location.origin}${basePath}/auth/callback`;
      const data = await api.auth.loginUrl(redirect);
      if (!data.oauth_available || !data.authorize_url) {
        throw new Error("GitHub sign-in is not configured. Use a personal access token below or contact your administrator.");
      }
      window.location.assign(data.authorize_url);
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Could not start GitHub sign-in.");
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!inputAccount.trim() || !inputToken.trim()) return;
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      await connectAccount(inputAccount.trim(), inputToken.trim());
      setInputToken("");
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Could not verify your account.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = useCallback(() => {
    setInputToken("");
    setErrorMsg(null);
    closeAccountModal();
  }, [closeAccountModal]);

  return (
    <Dialog isOpen={isModalOpen} onClose={handleClose} title="Sign in to Hadron" description="Authenticate to access reviews for your GitHub account.">
      {errorMsg && <div className="mb-4"><Alert variant="error" title="Sign-in failed" description={errorMsg} /></div>}
      <Button type="button" onClick={handleOAuthSignIn} isLoading={isSubmitting} variant="primary" className="w-full">Sign in with GitHub</Button>
      <details className="mt-5 border-t border-border pt-4">
        <summary className="cursor-pointer text-sm text-foreground">Use a personal access token</summary>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label htmlFor="modal-username" className="block text-sm text-foreground mb-1">GitHub username</label>
            <input id="modal-username" required autoComplete="username" value={inputAccount} onChange={(event) => setInputAccount(event.target.value)} className="w-full min-h-[44px] rounded-lg border border-border bg-panel px-3 text-foreground" />
          </div>
          <div>
            <label htmlFor="modal-token" className="block text-sm text-foreground mb-1">Personal access token</label>
            <input id="modal-token" type="password" required autoComplete="off" value={inputToken} onChange={(event) => setInputToken(event.target.value)} className="w-full min-h-[44px] rounded-lg border border-border bg-panel px-3 text-foreground" />
            <p className="text-xs text-muted mt-2">Your identity is verified with GitHub. Tokens are kept on the server.</p>
          </div>
          <Button type="submit" isLoading={isSubmitting} disabled={!inputAccount.trim() || !inputToken.trim()} className="w-full">Connect account</Button>
        </form>
      </details>
    </Dialog>
  );
}
