"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { mutate } from "swr";
import { api, clearClientTenantData } from "@/lib/api";
import type { AccountProfile, RepositoryItem } from "@/lib/types";

interface GitHubContextType {
  currentAccount: AccountProfile | null;
  isLoading: boolean;
  isModalOpen: boolean;
  repositories: RepositoryItem[];
  loadingRepos: boolean;
  repoError: string | null;
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
  const [repoError, setRepoError] = useState<string | null>(null);
  const generationRef = useRef<number>(0);
  const accountRef = useRef<AccountProfile | null>(null);
  accountRef.current = currentAccount;
  const openAccountModal = useCallback(() => setIsModalOpen(true), []);
  const closeAccountModal = useCallback(() => setIsModalOpen(false), []);

  // Restore identity from the server session, never from editable browser storage.
  useEffect(() => {
    const controller = new AbortController();
    const generation = generationRef.current;
    api.auth.me(controller.signal).then((profile) => {
      if (!controller.signal.aborted && generationRef.current === generation) setCurrentAccount(profile);
    }).catch(() => {
      if (!controller.signal.aborted && generationRef.current === generation) setCurrentAccount(null);
    }).finally(() => {
      if (!controller.signal.aborted) setIsLoading(false);
    });
    return () => controller.abort();
  }, []);

  // Fetch repositories whenever active account changes with generation guard against race responses
  const refreshRepos = useCallback(async () => {
    if (!currentAccount) {
      setRepositories([]);
      setRepoError(null);
      return;
    }
    const thisGen = ++generationRef.current;
    setLoadingRepos(true);
    setRepoError(null);
    try {
      const data = await api.auth.repos(currentAccount.login);
      if (generationRef.current === thisGen) {
        setRepositories(data);
        setRepoError(null);
      }
    } catch (err: unknown) {
      if (generationRef.current === thisGen) {
        const message = err instanceof Error ? err.message : "Failed to load account repositories";
        setRepoError(message);
        console.error("Failed to fetch account repositories", err);
      }
    } finally {
      if (generationRef.current === thisGen) {
        setLoadingRepos(false);
      }
    }
  }, [currentAccount]);

  useEffect(() => {
    if (currentAccount) {
      refreshRepos();
    }
  }, [currentAccount, refreshRepos]);

  const selectAccount = useCallback((profile: AccountProfile) => {
    generationRef.current++;
    // Purge cached data from prior tenant when switching accounts
    if (accountRef.current && accountRef.current.login !== profile.login) {
      generationRef.current++;
      setRepositories([]);
      setRepoError(null);
      mutate(() => true, undefined, { revalidate: false });
    }

    const safeProfile = { ...profile };
    delete safeProfile.token;
    setCurrentAccount(safeProfile);
    setIsModalOpen(false);
    try {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(TOKEN_KEY);
    } catch { /* Storage may be disabled. The server session remains authoritative. */ }
  }, []);

  const connectAccount = async (accountName: string, token?: string): Promise<AccountProfile> => {
    const profile = await api.auth.connect(accountName, token);
    selectAccount(profile);
    return profile;
  };

  const logout = async () => {
    generationRef.current++;
    try {
      await api.auth.logout();
    } catch {
      // Ignore network errors during logout
    }
    clearClientTenantData();
    mutate(() => true, undefined, { revalidate: false }); // Purge all cached user/review/cost data
    try {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(TOKEN_KEY);
    } catch { /* Storage may be disabled. */ }
    setCurrentAccount(null);
    setLoadingRepos(false);
    setRepositories([]);
    setRepoError(null);
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
        repoError,
        openAccountModal,
        closeAccountModal,
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
