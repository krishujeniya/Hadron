"use client";

import { useTheme, type Theme } from "@/lib/themeContext";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, resolvedTheme, setTheme } = useTheme();

  const cycleTheme = () => {
    if (theme === "dark") {
      setTheme("light");
    } else if (theme === "light") {
      setTheme("system");
    } else {
      setTheme("dark");
    }
  };

  const label =
    theme === "system"
      ? `Theme: System (${resolvedTheme} active). Click to switch to dark.`
      : theme === "dark"
      ? "Theme: Dark. Click to switch to light."
      : "Theme: Light. Click to switch to system.";

  return (
    <button
      type="button"
      onClick={cycleTheme}
      aria-label={label}
      title={label}
      className={`w-8 h-8 rounded-lg border border-border bg-panel hover:bg-surface text-muted hover:text-foreground flex items-center justify-center transition-all duration-150 active:scale-[0.98] focus:outline-none focus:ring-1 focus:ring-accent ${className}`}
    >
      {theme === "system" ? (
        // Monitor / System Icon
        <svg
          className="w-3.5 h-3.5 text-accent"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      ) : theme === "dark" ? (
        // Sun Icon for Dark Mode (click to switch to light)
        <svg
          className="w-3.5 h-3.5 text-warn"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      ) : (
        // Moon Icon for Light Mode (click to switch to system/dark)
        <svg
          className="w-3.5 h-3.5 text-accent"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      )}
    </button>
  );
}
