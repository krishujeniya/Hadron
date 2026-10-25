"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useGitHubAccount } from "@/lib/githubContext";
import { Empty } from "@/components/Empty";

export default function RepositoriesPage() {
  const { currentAccount, repositories, loadingRepos, refreshRepos, openAccountModal } = useGitHubAccount();
  const [searchTerm, setSearchTerm] = useState("");

  if (!currentAccount) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Account Repositories</h1>
          <p className="text-muted text-sm mt-1">Please connect or select a GitHub account first.</p>
        </div>
        <div className="border border-border rounded-lg bg-panel p-8 text-center space-y-4">
          <p className="text-muted text-sm">No GitHub account selected to inspect repositories.</p>
          <button
            onClick={openAccountModal}
            className="bg-accent hover:bg-accent/90 text-white font-medium text-sm py-2 px-4 rounded-lg transition"
          >
            Select GitHub Account
          </button>
        </div>
      </div>
    );
  }

  const filtered = repositories.filter(
    (r) =>
      r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.description && r.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold">Repositories</h1>
            <span className="font-mono text-xs text-accent bg-accent/10 border border-accent/20 px-2 py-0.5 rounded-full">
              @{currentAccount.login}
            </span>
          </div>
          <p className="text-muted text-sm mt-1">
            Displaying all repositories belonging to <span className="font-mono text-white">@{currentAccount.login}</span>. Hadron is scoped to this account.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => refreshRepos()}
            disabled={loadingRepos}
            className="px-3 py-1.5 border border-border rounded-lg text-xs font-mono text-muted hover:text-white hover:bg-bg transition disabled:opacity-50"
          >
            {loadingRepos ? "Refreshing..." : "↻ Refresh"}
          </button>
          <button
            onClick={openAccountModal}
            className="px-3 py-1.5 bg-accent/10 border border-accent/30 rounded-lg text-xs font-medium text-accent hover:bg-accent/20 transition"
          >
            Switch Account
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Filter repositories by name or description..."
          className="bg-panel border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-muted/60 focus:outline-none focus:border-accent w-full max-w-md font-mono"
        />
        <span className="text-xs text-muted">
          {filtered.length} of {repositories.length} repos
        </span>
      </div>

      {/* Repository Grid */}
      {loadingRepos && repositories.length === 0 ? (
        <Empty>Loading repositories for @{currentAccount.login}...</Empty>
      ) : filtered.length === 0 ? (
        <Empty>
          {searchTerm
            ? `No repositories match "${searchTerm}".`
            : `No repositories found for @${currentAccount.login}.`}
        </Empty>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((repo) => (
            <div
              key={repo.id}
              className="border border-border rounded-lg bg-panel p-4 flex flex-col justify-between hover:border-accent/40 transition"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div className="font-mono text-base font-medium text-white hover:text-accent">
                    <a href={repo.html_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5">
                      <span>{repo.name}</span>
                      <svg className="w-3.5 h-3.5 text-muted opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  </div>
                  {repo.private ? (
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-warn/15 text-warn border border-warn/30">
                      Private
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-bg text-muted border border-border">
                      Public
                    </span>
                  )}
                </div>

                <p className="text-muted text-xs mt-2 line-clamp-2 min-h-[32px]">
                  {repo.description || "No description provided."}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs text-muted">
                <div className="flex items-center gap-3 font-mono text-[11px]">
                  <span title="Stars" className="flex items-center gap-1">
                    ★ {repo.stargazers_count}
                  </span>
                  <span title="Open Issues & PRs" className="flex items-center gap-1">
                    ⑂ {repo.open_issues_count}
                  </span>
                  <span className="text-muted/60">
                    branch: {repo.default_branch}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Link
                    href={`/reviews?repo=${encodeURIComponent(repo.full_name)}`}
                    className="text-xs text-accent hover:underline font-mono"
                  >
                    Reviews →
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
