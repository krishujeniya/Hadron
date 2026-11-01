"use client";

import { SWRConfig } from "swr";
import { fetcher } from "./api";

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher,
        revalidateOnFocus: true,
        revalidateOnReconnect: true,
        dedupingInterval: 2000,
        shouldRetryOnError: true,
        errorRetryCount: 3,
        onErrorRetry: (error, _key, _config, revalidate, { retryCount }) => {
          // Do not retry authorization, forbidden, not found, or validation errors
          if (
            error?.status === 401 ||
            error?.status === 403 ||
            error?.status === 404 ||
            error?.status === 422
          ) {
            return;
          }

          // Bounded retry loop (Gate B/C: max 3 attempts)
          if (retryCount >= 3) return;

          // Pause retries when tab is in background or device is offline
          if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
          if (typeof navigator !== "undefined" && !navigator.onLine) return;

          // Exponential backoff with jitter (1s, 2s, 4s, capped at 8s)
          const timeout = Math.min(1000 * 2 ** retryCount, 8000);
          setTimeout(() => revalidate({ retryCount }), timeout);
        },
      }}
    >
      {children}
    </SWRConfig>
  );
}
