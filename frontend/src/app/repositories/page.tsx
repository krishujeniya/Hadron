"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useGitHubAccount } from "@/lib/githubContext";
import { Empty } from "@/components/Empty";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Status } from "@/components/ui/Status";

export default function RepositoriesPage() {
  const { currentAccount, repositories, loadingRepos, refreshRepos, openAccountModal } = useGitHubAccount();
  const [searchTerm, setSearchTerm] = useState("");

  if (!currentAccount) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-foreground font-mono">Account Repositories</h1>
          <p className="text-muted text-sm mt-1">Please connect or select a GitHub account first.</p>
        </div>
        <div className="border border-border rounded-xl bg-surface p-8 text-center space-y-4 shadow-sm">
          <p className="text-muted text-sm">No GitHub account selected to inspect repositories.</p>
          <Button
            onClick={openAccountModal}
            variant="primary"
          >
            Select GitHub Account
          </Button>
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
      <PageHeader
        tag={`Workspace @${currentAccount.login}`}
        title="Repositories"
        description={`Displaying all repositories belonging to @${currentAccount.login}. Hadron is scoped to this workspace.`}
        actions={
          <>
            <Button
              onClick={() => refreshRepos()}
              disabled={loadingRepos}
              variant="secondary"
              size="sm"
            >
              {loadingRepos ? "Refreshing..." : "↻ Refresh"}
            </Button>
            <Button
              onClick={openAccountModal}
              variant="primary"
              size="sm"
            >
              Switch Account
            </Button>
          </>
        }
      />

      {/* Search Bar */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Filter repositories by name or description..."
          className="bg-surface border border-border rounded-xl px-3.5 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:border-accent w-full max-w-md font-mono"
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
              className="border border-border rounded-xl bg-surface p-4 flex flex-col justify-between hover:border-muted/50 transition-all shadow-sm"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div className="font-mono text-base font-semibold text-foreground hover:text-accent min-w-0 break-all">
                    <a href={repo.html_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 flex-wrap">
                      <span>{repo.name}</span>
                      <svg className="w-3.5 h-3.5 text-muted opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {repo.status === "active" ? (
                      <Status variant="success" label={`Active (${repo.review_count || 0})`} />
                    ) : repo.status === "indexing" ? (
                      <Status variant="warning" label="Indexing" />
                    ) : repo.status === "degraded" ? (
                      <Status variant="error" label="Degraded" />
                    ) : repo.status === "connected" ? (
                      <Status variant="info" label="Connected" />
                    ) : (
                      <Status variant="neutral" label="Discovered" />
                    )}
                    {repo.private ? (
                      <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-panel text-muted border border-border">
                        Private
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-panel text-muted border border-border">
                        Public
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-muted text-xs mt-2 line-clamp-2 min-h-[32px]">
                  {repo.description || "No description provided."}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-separator flex items-center justify-between text-xs text-muted">
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
