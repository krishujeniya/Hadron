/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === "production";
const configuredApi = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "";

// Fail unsafe production defaults when bypassing proxy without an explicit API host
if (isProd && process.env.NEXT_PUBLIC_API_DIRECT === "1" && !configuredApi) {
  throw new Error(
    "NEXT_PUBLIC_API_BASE_URL must be explicitly configured when NEXT_PUBLIC_API_DIRECT=1 in production. " +
    "Silent fallbacks to third-party endpoints are prohibited."
  );
}

// In local development default to local backend; in production default to live backend or configured host
const DEFAULT_BACKEND = isProd ? "https://hadron-backend.vercel.app" : "http://localhost:8000";
const API_BASE = configuredApi || DEFAULT_BACKEND;

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https: blob:",
              "font-src 'self' data:",
              "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 https://hadron-backend.vercel.app " + (configuredApi || ""),
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
      {
        source: "/api/:path*",
        headers: [
          { key: "Cache-Control", value: "no-store, no-cache, must-revalidate, private" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_BASE}/api/:path*` },
      { source: "/health/:path*", destination: `${API_BASE}/health/:path*` },
    ];
  },
};

export default nextConfig;
