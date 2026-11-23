export async function onRequest(context: any) {
  const request = context.request;
  const url = new URL(request.url);

  // If OPTIONS preflight, return early with CORS
  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-CSRF-Token, X-Account",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  // Forward to Backend Pages Project
  const UPSTREAM = "https://api-hadron-pr.pages.dev";
  const targetUrl = new URL(url.pathname + url.search, UPSTREAM);

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
    newHeaders.set("Access-Control-Allow-Origin", "*");
    newHeaders.set("Access-Control-Allow-Credentials", "true");

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  } catch (err: any) {
    return new Response(
      JSON.stringify({ error: "Pages API Proxy Error", details: err?.message || String(err) }),
      {
        status: 502,
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
      }
    );
  }
}
