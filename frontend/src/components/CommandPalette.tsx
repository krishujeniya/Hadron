"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useGitHubAccount } from "@/lib/githubContext";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const router = useRouter();
  const { currentAccount, openAccountModal } = useGitHubAccount();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const actions = [
    { id: "dash", category: "Navigation", label: "Dashboard (Executive Health)", icon: "📊", action: () => router.push("/") },
    { id: "approvals", category: "Navigation", label: "Approvals & Sign-Offs (Action Needed)", icon: "⚡", action: () => router.push("/hitl") },
    { id: "reviews", category: "Navigation", label: "All Pull Request Reviews", icon: "📋", action: () => router.push("/reviews") },
    { id: "repos", category: "Navigation", label: "Watched Repositories", icon: "📂", action: () => router.push("/repositories") },
    { id: "economics", category: "Navigation", label: "Economics & Cloud Cost Guardrails", icon: "💰", action: () => router.push("/economics") },
    { id: "health", category: "Navigation", label: "Hadron Engine Health & Uptime", icon: "🟢", action: () => router.push("/health") },
    {
      id: "mode-exec",
      category: "View Mode",
      label: "Switch to Plain English (Non-Tech Executive View)",
      icon: "✨",
      action: () => {
        localStorage.setItem("hadron_view_mode", "executive");
        window.dispatchEvent(new Event("storage"));
        router.push("/");
      },
    },
    {
      id: "mode-dev",
      category: "View Mode",
      label: "Switch to Developer View (Telemetry & Diffs)",
      icon: "⚡",
      action: () => {
        localStorage.setItem("hadron_view_mode", "developer");
        window.dispatchEvent(new Event("storage"));
        router.push("/");
      },
    },
    { id: "switch-acc", category: "Account", label: "Switch GitHub Organization / Account", icon: "👤", action: () => openAccountModal() },
  ];

  const filtered = actions.filter((item) =>
    item.label.toLowerCase().includes(query.toLowerCase()) ||
    item.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + (filtered.length || 1)) % (filtered.length || 1));
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        filtered[selectedIndex].action();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, selectedIndex, filtered, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/75 backdrop-blur-md transition-opacity">
      <div
        className="w-full max-w-xl rounded-2xl border border-white/20 bg-gradient-to-b from-zinc-900/95 via-zinc-950 to-black p-4 shadow-2xl shadow-black/80 space-y-3 relative overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-3 py-2 border-b border-white/10">
          <span className="text-zinc-400 text-sm">🔍</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a command or jump to page... (e.g. 'Approvals', 'Executive')"
            className="w-full bg-transparent text-sm text-white placeholder-zinc-500 focus:outline-none"
          />
          <kbd className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/10 text-zinc-400 border border-white/10">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-72 overflow-y-auto space-y-1 pr-1">
          {filtered.length === 0 ? (
            <div className="p-6 text-center text-xs text-zinc-500">
              No matching commands or pages found.
            </div>
          ) : (
            filtered.map((item, index) => {
              const isSelected = index === selectedIndex;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    item.action();
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left text-xs transition-all ${
                    isSelected
                      ? "bg-white text-black font-semibold shadow-sm"
                      : "text-zinc-300 hover:bg-white/[0.04]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="text-base">{item.icon}</span>
                    <span className="truncate">{item.label}</span>
                  </div>
                  <span
                    className={`text-[10px] font-mono uppercase tracking-wider shrink-0 px-1.5 py-0.5 rounded border ${
                      isSelected ? "border-black/30 text-black/70" : "border-white/10 text-zinc-500"
                    }`}
                  >
                    {item.category}
                  </span>
                </button>
              );
            })
          )}
        </div>

        {/* Footer shortcuts helper */}
        <div className="flex items-center justify-between pt-2 border-t border-white/10 text-[10px] text-zinc-500 font-mono">
          <div className="flex items-center gap-3">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
          </div>
          <span>Hadron Command Engine</span>
        </div>
      </div>
    </div>
  );
}
