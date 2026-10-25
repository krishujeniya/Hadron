import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://hadron.dev";

  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/solutions/", "/health"],
        disallow: ["/reviews/", "/hitl/", "/auth/", "/api/"],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
