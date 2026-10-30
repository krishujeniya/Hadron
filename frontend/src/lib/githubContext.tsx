"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import type { AccountProfile, RepositoryItem } from "./types";

interface GitHubContextType {
  currentAccount: AccountProfile | null;
  isLoading: boolean;
  isModalOpen: boolean;
  repositories: RepositoryItem[];
  loadingRepos: boolean;
  openAccountModal: () => void;
  closeAccountModal: () => void;
  selectAccount: (profile: AccountProfile, token?: string) => void;
  connectAccount: (accountName: string, token?: string) => Promise<AccountProfile>;
  logout: () => void;
  refreshRepos: () => Promise<void>;
}

const GitHubContext = createContext<GitHubContextType | undefined>(undefined);

const STORAGE_KEY = "ai_pr_review_github_account";
const TOKEN_KEY = "ai_pr_review_github_token";

export function GitHubProvider({ children }: { children: React.ReactNode }) {
  const [currentAccount, setCurrentAccount] = useState<AccountProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [repositories, setRepositories] = useState<RepositoryItem[]>([]);
  const [loadingRepos, setLoadingRepos] = useState<boolean>(false);

  // Load saved account on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed: AccountProfile = JSON.parse(saved);
        setCurrentAccount(parsed);
      } else {
        // No account saved — prompt user on initial load
        setIsModalOpen(true);
      }
    } catch (e) {
      console.warn("Failed to read saved GitHub account", e);
      setIsModalOpen(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch repositories whenever active account changes
  const refreshRepos = useCallback(async () => {
    if (!currentAccount) {
      setRepositories([]);
      return;
    }
    setLoadingRepos(true);
    try {
      // Backend automatically checks HttpOnly session cookie 'hadron_session'
      const res = await fetch(`/api/v1/auth/repos?account=${encodeURIComponent(currentAccount.login)}`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setRepositories(data);
      }
    } catch (err) {
      console.error("Failed to fetch account repositories", err);
    } finally {
      setLoadingRepos(false);
    }
  }, [currentAccount]);

  useEffect(() => {
    if (currentAccount) {
      refreshRepos();
    }
  }, [currentAccount, refreshRepos]);

  const selectAccount = (profile: AccountProfile, token?: string) => {
    // Keep in-memory for active session without exposing plaintext secrets to localStorage
    const profileToSave = { ...profile };
    delete profileToSave.token; // Never persist tokens to localStorage
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profileToSave));

    if (token) {
      profile.token = token;
    }
    setCurrentAccount(profile);
    setIsModalOpen(false);
  };

  const connectAccount = async (accountName: string, token?: string): Promise<AccountProfile> => {
    const res = await fetch("/api/v1/auth/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account: accountName, token }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to connect GitHub account");
    }

    const profile: AccountProfile = await res.json();
    selectAccount(profile, token);
    return profile;
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(TOKEN_KEY);
    setCurrentAccount(null);
    setRepositories([]);
    setIsModalOpen(true);
  };

  return (
    <GitHubContext.Provider
      value={{
        currentAccount,
        isLoading,
        isModalOpen,
        repositories,
        loadingRepos,
        openAccountModal: () => setIsModalOpen(true),
        closeAccountModal: () => {
          if (currentAccount) setIsModalOpen(false);
        },
        selectAccount,
        connectAccount,
        logout,
        refreshRepos,
      }}
    >
      {children}
    </GitHubContext.Provider>
  );
}

export function useGitHubAccount() {
  const context = useContext(GitHubContext);
  if (!context) {
    throw new Error("useGitHubAccount must be used within a GitHubProvider");
  }
  return context;
}
