export interface Env {
  AI: any;
  DB: D1Database;
  CONFIG_KV: KVNamespace;
  UPSTREAM_API?: string;
}

const UPSTREAM_DEFAULT = "https://hadron-backend.vercel.app";

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-CSRF-Token, X-Account",
  "Access-Control-Allow-Credentials": "true",
  "Access-Control-Max-Age": "86400",
};

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: CORS_HEADERS,
      });
    }

    const url = new URL(request.url);

    // Direct edge health check
    if (url.pathname === "/healthz") {
      return new Response(
        JSON.stringify({
          status: "healthy",
          service: "hadron-edge-gateway",
          upstream: env.UPSTREAM_API || UPSTREAM_DEFAULT,
          timestamp: new Date().toISOString(),
        }),
        {
          headers: {
            "Content-Type": "application/json",
            ...CORS_HEADERS,
          },
        }
      );
    }

    // Proxy API and health routes to the full FastAPI backend on Vercel
    const upstreamBase = env.UPSTREAM_API || UPSTREAM_DEFAULT;
    const targetUrl = new URL(url.pathname + url.search, upstreamBase);

    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", url.host);
    headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

    try {
      const response = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: headers,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "follow",
      });

      const newHeaders = new Headers(response.headers);
      for (const [key, val] of Object.entries(CORS_HEADERS)) {
        newHeaders.set(key, val);
      }

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: newHeaders,
      });
    } catch (err: any) {
      return new Response(
        JSON.stringify({
          error: "Edge Gateway upstream connection error",
          details: err?.message || String(err),
        }),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json",
            ...CORS_HEADERS,
          },
        }
      );
    }
  },
};
