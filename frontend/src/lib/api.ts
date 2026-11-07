// Typed API client. Single boundary between frontend and backend (Law of Demeter).
// All fetches go through here so swapping transport (polling -> SSE) is one file.

import type {
  AccountProfile,
  BudgetStatus,
  DailyPoint,
  EconomicsSummary,
  HITLDecisionRequest,
  HITLDecisionResponse,
  HITLDetail,
  HITLItem,
  HealthLiveResponse,
  HealthStatusResponse,
  Paginated,
  ReviewDetail,
  ReviewSummary,
  WorkflowCost,
} from "./types";

// Origin and direct API resolution:
// When running on GitHub Pages (*.github.io) or when NEXT_PUBLIC_API_DIRECT=1 is set,
// all API requests dispatch directly to the production FastAPI backend (https://hadron-backend.vercel.app).
const isClient = typeof window !== "undefined";
const isGitHubPages = isClient && (window.location.hostname.endsWith("github.io") || window.location.pathname.startsWith("/Hadron"));

const configuredApi =
  (typeof process !== "undefined" && (process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL)) ||
  "";

const isDirect =
  isGitHubPages ||
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_DIRECT === "1");

const DEFAULT_BACKEND = "https://hadron-backend.vercel.app";
export const API_BASE_URL = isDirect ? (configuredApi || DEFAULT_BACKEND) : (configuredApi || "");
const BASE = API_BASE_URL;

const SESSION_STORAGE_KEY = "hadron_session_token";
const CSRF_STORAGE_KEY = "hadron_csrf_token";
const OAUTH_STATE_KEY = "hadron_oauth_state";

export function getSessionToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(SESSION_STORAGE_KEY) || sessionStorage.getItem(SESSION_STORAGE_KEY) || null;
  } catch {
    return null;
  }
}

export function setSessionToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      localStorage.setItem(SESSION_STORAGE_KEY, token);
      sessionStorage.setItem(SESSION_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    }
  } catch {}
}

export function getStoredCsrfToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(CSRF_STORAGE_KEY) || sessionStorage.getItem(CSRF_STORAGE_KEY) || null;
  } catch {
    return null;
  }
}

export function setStoredCsrfToken(csrf: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (csrf) {
      localStorage.setItem(CSRF_STORAGE_KEY, csrf);
      sessionStorage.setItem(CSRF_STORAGE_KEY, csrf);
    } else {
      localStorage.removeItem(CSRF_STORAGE_KEY);
      sessionStorage.removeItem(CSRF_STORAGE_KEY);
    }
  } catch {}
}

export function getOAuthState(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(OAUTH_STATE_KEY) || localStorage.getItem(OAUTH_STATE_KEY) || null;
  } catch {
    return null;
  }
}

export function setOAuthState(state: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (state) {
      sessionStorage.setItem(OAUTH_STATE_KEY, state);
      localStorage.setItem(OAUTH_STATE_KEY, state);
    } else {
      sessionStorage.removeItem(OAUTH_STATE_KEY);
      localStorage.removeItem(OAUTH_STATE_KEY);
    }
  } catch {}
}

export class ApiError extends Error {
  readonly status: number;
  readonly statusText: string;
  readonly code: string;
  readonly requestId?: string;
  readonly details?: unknown;
  readonly rawBody?: string;

  constructor(
    status: number,
    statusText: string,
    message: string,
    code?: string,
    requestId?: string,
    details?: unknown,
    rawBody?: string
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.code = code || `HTTP_${status}`;
    this.requestId = requestId;
    this.details = details;
    this.rawBody = rawBody;
  }

  get isUnauthorized() { return this.status === 401; }
  get isForbidden() { return this.status === 403; }
  get isNotFound() { return this.status === 404; }
  get isConflict() { return this.status === 409; }
  get isValidationError() { return this.status === 422; }
  get isRateLimited() { return this.status === 429; }
  get isServerError() { return this.status >= 500; }
}

function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|; )hadron_csrf=([^;]*)/);
  if (match) return decodeURIComponent(match[1]);
  return getStoredCsrfToken();
}

function createRequestId(): string {
  return `req-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 8)}`;
}

function headers(): Record<string, string> {
  const h: Record<string, string> = {
    "content-type": "application/json",
    "x-request-id": createRequestId(),
  };
  const sessionToken = getSessionToken();
  if (sessionToken) {
    h["Authorization"] = `Bearer ${sessionToken}`;
  }
  const csrf = getCsrfToken();
  if (csrf) h["x-csrf-token"] = csrf;
  return h;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const reqHeaders = { ...headers(), ...(init?.headers ?? {}) };
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: reqHeaders,
    cache: "no-store",
  });

  if (!res.ok) {
    const rawBody = await res.text().catch(() => "");
    let errorJson: any = null;
    try {
      errorJson = rawBody ? JSON.parse(rawBody) : null;
    } catch {
      // Non-JSON response (e.g. proxy gateway error)
    }

    const message =
      errorJson?.error?.message ||
      errorJson?.detail ||
      `${res.status} ${res.statusText}`;
    const code = errorJson?.error?.code || `HTTP_${res.status}`;
    const requestId =
      errorJson?.error?.request_id ||
      res.headers.get("x-request-id") ||
      (reqHeaders as Record<string, string>)["x-request-id"];
    const details = errorJson?.error?.details || errorJson?.detail;

    throw new ApiError(
      res.status,
      res.statusText,
      message,
      code,
      requestId,
      details,
      rawBody
    );
  }

  return (await res.json()) as T;
}

// SWR fetcher (single-arg)
export const fetcher = <T>(path: string) => req<T>(path);

export function ensurePaginated<T>(data: any): Paginated<T> {
  if (!data || typeof data !== "object") {
    return { items: [], total: 0, limit: 50, offset: 0, next_cursor: null };
  }
  return {
    items: Array.isArray(data.items) ? data.items : [],
    total: typeof data.total === "number" ? data.total : (Array.isArray(data.items) ? data.items.length : 0),
    limit: typeof data.limit === "number" ? data.limit : 50,
    offset: typeof data.offset === "number" ? data.offset : 0,
    next_cursor: typeof data.next_cursor === "string" ? data.next_cursor : null,
  };
}

// Encode a "owner/repo:pr:sha" id for a URL path segment.
// Backend matches on the raw colon-separated id; we URL-encode the slash and colons.
export const encodeReviewId = (id: string) => encodeURIComponent(id);

export function clearClientTenantData(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.clear();
    localStorage.removeItem(SESSION_STORAGE_KEY);
    localStorage.removeItem(CSRF_STORAGE_KEY);
    localStorage.removeItem(OAUTH_STATE_KEY);
    localStorage.removeItem("github_account_profile");
    localStorage.removeItem("github_access_token");
    localStorage.removeItem("hadron_active_tenant");
  } catch {
    // Storage access blocked or restricted
  }
}

export const api = {
  // ── Auth ─────────────────────────────────────────────────────────
  auth: {
    loginUrl: async (redirectUri?: string) => {
      const query = redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : "";
      const res = await req<{ oauth_available: boolean; authorize_url?: string; state?: string }>(
        `/api/v1/auth/github/login${query}`
      );
      if (res.state) {
        setOAuthState(res.state);
      }
      return res;
    },
    callback: async (code: string, state: string) => {
      const headersInit: Record<string, string> = {};
      const savedState = getOAuthState() || state;
      if (savedState) {
        headersInit["X-OAuth-State"] = savedState;
      }
      const profile = await req<AccountProfile>("/api/v1/auth/github/callback", {
        method: "POST",
        headers: headersInit,
        body: JSON.stringify({ code, state }),
      });
      if (profile.session_token) {
        setSessionToken(profile.session_token);
      }
      if (profile.csrf_token) {
        setStoredCsrfToken(profile.csrf_token);
      }
      setOAuthState(null);
      return profile;
    },
    me: (signal?: AbortSignal) => req<AccountProfile>("/api/v1/auth/me", { signal }),
    logout: async () => {
      try {
        await req<{ status: string }>("/api/v1/auth/logout", { method: "POST" });
      } finally {
        setSessionToken(null);
        setStoredCsrfToken(null);
        clearClientTenantData();
      }
      return { status: "logged_out" };
    },
    repos: (account: string, signal?: AbortSignal) =>
      req<any[]>(`/api/v1/auth/repos?account=${encodeURIComponent(account)}`, { signal }),
    connect: async (account: string, token?: string) => {
      const profile = await req<AccountProfile>("/api/v1/auth/connect", {
        method: "POST",
        body: JSON.stringify({ account, token }),
      });
      if (profile.session_token) {
        setSessionToken(profile.session_token);
      }
      if (profile.csrf_token) {
        setStoredCsrfToken(profile.csrf_token);
      }
      return profile;
    },
  },

  healthLive: () => req<HealthLiveResponse>("/health/live"),
  healthReady: () => req<HealthStatusResponse>("/health/ready"),
  health: () => req<HealthStatusResponse>("/health/ready"),

  listReviews: (limit = 50, offset = 0, cursor?: string, signal?: AbortSignal) =>
    req<Paginated<ReviewSummary>>(
      `/api/v1/reviews?limit=${limit}&offset=${offset}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
      { signal }
    ),
  getReview: (id: string, signal?: AbortSignal) =>
    req<ReviewDetail>(`/api/v1/reviews/${encodeReviewId(id)}`, { signal }),

  hitlQueue: (limit = 50, offset = 0, signal?: AbortSignal) =>
    req<Paginated<HITLItem>>(
      `/api/v1/hitl/queue?limit=${limit}&offset=${offset}`,
      { signal }
    ),
  hitlGet: (id: string, signal?: AbortSignal) =>
    req<HITLDetail>(`/api/v1/hitl/${encodeURIComponent(id)}`, { signal }),
  hitlDecide: (id: string, body: HITLDecisionRequest) =>
    req<HITLDecisionResponse>(
      `/api/v1/hitl/${encodeURIComponent(id)}/decision`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  hitlRebuild: () =>
    req<{ rebuilt: number; pushed_to_redis?: number; message?: string }>("/api/v1/hitl/queue/rebuild", { method: "POST" }),

  // ── Phase 16: Economics ────────────────────────────────────────
  econSummary: (signal?: AbortSignal) => req<EconomicsSummary>("/api/v1/economics/summary", { signal }),
  econBudget: (signal?: AbortSignal) => req<BudgetStatus>("/api/v1/economics/budget", { signal }),
  econTimeseries: (days = 30, signal?: AbortSignal) =>
    req<DailyPoint[]>(`/api/v1/economics/timeseries?days=${days}`, { signal }),
  econWorkflow: (workflowId: string, signal?: AbortSignal) =>
    req<WorkflowCost>(
      `/api/v1/economics/workflow/${encodeURIComponent(workflowId)}`,
      { signal }
    ),
};
