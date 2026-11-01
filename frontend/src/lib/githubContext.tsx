"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { mutate } from "swr";
import { api, clearClientTenantData } from "./api";
import type { AccountProfile, RepositoryItem } from "./types";

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

  const selectAccount = (profile: AccountProfile, token?: string) => {
    // Purge cached data from prior tenant when switching accounts
    if (currentAccount && currentAccount.login !== profile.login) {
      generationRef.current++;
      setRepositories([]);
      setRepoError(null);
      mutate(() => true, undefined, { revalidate: false });
    }

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
    const profile = await api.auth.connect(accountName, token);
    selectAccount(profile, token);
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
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(TOKEN_KEY);
    setCurrentAccount(null);
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
