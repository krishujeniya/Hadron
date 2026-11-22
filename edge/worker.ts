export interface Env {
  AI: any;
  DB: D1Database;
  CONFIG_KV: KVNamespace;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/healthz" || url.pathname === "/health") {
      return new Response(JSON.stringify({ status: "healthy", service: "hadron-edge" }), {
        headers: { "Content-Type": "application/json" }
      });
    }
    return new Response(JSON.stringify({ message: "Hadron Edge API running on Cloudflare" }), {
      headers: { "Content-Type": "application/json" }
    });
  }
};
