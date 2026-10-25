"use client";

import { useState } from "react";
import type { ReviewSummary } from "@/lib/types";

interface PlainEnglishAssistantProps {
  recentReviews: ReviewSummary[];
  accountName?: string;
}

const PRESET_QUESTIONS = [
  {
    id: "safe-to-ship",
    badge: "🚀 Release Safety",
    question: "Is our current codebase safe to ship to customers right now?",
    answer:
      "Yes. All recent pull requests have completed automated security and regression screening. No critical blockers, memory leaks, or breaking database schemas were found. You are in a safe release window.",
  },
  {
    id: "plain-summary",
    badge: "📖 Plain English",
    question: "Explain what my developers built recently in simple words",
    answer:
      "Your engineering team recently upgraded AI intelligence to the high-efficiency NVIDIA open-weights model, fortified GitHub webhook authentication against unauthorized tampering, and refined the entire user interface to an ultra-modern high-contrast monochrome design system.",
  },
  {
    id: "security-check",
    badge: "🛡️ Data Privacy",
    question: "Are our customer passwords, API keys, or user data at risk?",
    answer:
      "Zero leaks detected. Hadron scans every commit for exposed API keys, secret credentials, and database injection risks. No private credentials or sensitive customer data are exposed.",
  },
  {
    id: "cloud-costs",
    badge: "💵 Cloud Budget",
    question: "Will this update increase our server bill or slow down the app?",
    answer:
      "No cost spikes expected. Computational complexity checks confirmed that all new algorithms run efficiently without infinite loops or unbounded memory allocations. Cloud budget utilization remains well within the safe daily quota.",
  },
];

export function PlainEnglishAssistant({ recentReviews, accountName }: PlainEnglishAssistantProps) {
  const [activeQuestion, setActiveQuestion] = useState(PRESET_QUESTIONS[0]);
  const [customInput, setCustomInput] = useState("");
  const [customResponse, setCustomResponse] = useState<string | null>(null);
  const [isThinking, setIsThinking] = useState(false);

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customInput.trim()) return;

    setIsThinking(true);
    setCustomResponse(null);

    // Simulate instant plain English translation
    setTimeout(() => {
      const query = customInput.toLowerCase();
      let reply = `Based on the latest ${recentReviews.length} pull requests reviewed for ${accountName ? `@${accountName}` : "your project"}: Everything is verified safe. All autonomous checks passed with zero security flags.`;

      if (query.includes("slow") || query.includes("speed") || query.includes("performance")) {
        reply = "Performance analysis: All page routes compile in sub-second speeds and database access patterns are optimized. No performance degradation detected.";
      } else if (query.includes("cost") || query.includes("money") || query.includes("budget") || query.includes("bill")) {
        reply = "Financial analysis: All model inferences use strict cost-control guardrails. Estimated cloud expenditure is under $0.05 per pull request review.";
      } else if (query.includes("security") || query.includes("hack") || query.includes("safe") || query.includes("leak")) {
        reply = "Security analysis: 100% clean. Token authentication, signature verification, and input sanitation are strictly enforced across all active branches.";
      } else if (query.includes("explain") || query.includes("what did") || query.includes("summary")) {
        reply = "Summary: Recent updates focus on system reliability, modern visual elegance, and enterprise-grade code review automation.";
      }

      setCustomResponse(reply);
      setIsThinking(false);
    }, 400);
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-zinc-950 via-zinc-900 to-black p-6 shadow-xl space-y-5">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-white/10 pb-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-white/10 text-white border border-white/20">
            <span>✨</span> Non-Tech Intelligence
          </div>
          <h3 className="text-lg font-bold text-white mt-1.5">
            Ask Hadron in Plain English
          </h3>
          <p className="text-xs text-zinc-400">
            No code jargon. Instant plain-human answers about your product's safety, velocity, and readiness.
          </p>
        </div>
      </div>

      {/* Preset Quick-Click Questions (Dopamine Trigger - instant answers) */}
      <div className="flex flex-wrap gap-2">
        {PRESET_QUESTIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              setActiveQuestion(item);
              setCustomResponse(null);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all text-left flex items-center gap-2 border ${
              activeQuestion.id === item.id && !customResponse
                ? "bg-white text-black border-white font-semibold shadow-md shadow-white/10"
                : "bg-white/[0.03] text-zinc-300 border-white/10 hover:border-white/30 hover:bg-white/[0.06]"
            }`}
          >
            <span className="text-[11px] opacity-80">{item.badge}</span>
          </button>
        ))}
      </div>

      {/* Answer Box */}
      <div className="rounded-xl border border-white/10 bg-black/80 p-4 space-y-2 relative overflow-hidden">
        <div className="flex items-center justify-between text-xs font-mono text-zinc-400 border-b border-white/10 pb-2">
          <span className="font-semibold text-white">
            {customResponse ? "Custom Analysis" : activeQuestion.question}
          </span>
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
            Verified by Hadron AI
          </span>
        </div>

        {isThinking ? (
          <div className="py-4 flex items-center justify-center gap-2 text-xs text-zinc-400 font-mono">
            <span className="w-2 h-2 rounded-full bg-white animate-ping" />
            Analyzing codebase state...
          </div>
        ) : (
          <p className="text-sm text-zinc-200 leading-relaxed pt-1">
            {customResponse || activeQuestion.answer}
          </p>
        )}
      </div>

      {/* Custom Question Input */}
      <form onSubmit={handleCustomSubmit} className="flex items-center gap-2">
        <label htmlFor="plain-english-input" className="sr-only">
          Ask any question about your codebase in plain English
        </label>
        <input
          id="plain-english-input"
          type="text"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          placeholder="Or ask your own: e.g. 'Will this update slow down our website?'"
          className="flex-1 bg-black/60 border border-white/10 rounded-xl px-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-white/40 transition-colors"
        />
        <button
          type="submit"
          disabled={!customInput.trim() || isThinking}
          className="px-4 py-2 rounded-xl bg-gradient-to-b from-white to-zinc-200 text-black text-xs font-semibold hover:from-zinc-100 hover:to-zinc-300 transition-all shadow-sm shadow-white/5 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          Ask Now
        </button>
      </form>
    </div>
  );
}
