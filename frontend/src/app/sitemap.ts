import { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://hadron.dev";
  const now = new Date();

  const frameworkSolutions = [
    "python-security-audit",
    "nextjs-pr-review",
    "fastapi-code-quality",
    "go-concurrency-checker",
  ];

  const solutionUrls: MetadataRoute.Sitemap = frameworkSolutions.map((slug) => ({
    url: `${baseUrl}/solutions/${slug}`,
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.9,
  }));

  return [
    {
      url: baseUrl,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 1.0,
    },
    {
      url: `${baseUrl}/health`,
      lastModified: now,
      changeFrequency: "hourly" as const,
      priority: 0.5,
    },
    ...solutionUrls,
  ];
}
