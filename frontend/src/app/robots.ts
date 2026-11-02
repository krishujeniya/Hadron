import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://hadron.vercel.app";

  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/solutions/", "/llms.txt"],
        disallow: [
          "/health/",
          "/economics/",
          "/repositories/",
          "/reviews/",
          "/hitl/",
          "/auth/",
          "/api/",
        ],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
