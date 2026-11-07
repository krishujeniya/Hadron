import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from "react";

interface RouterContextType {
  pathname: string;
  searchParams: URLSearchParams;
  params: Record<string, string>;
  push: (href: string) => void;
  replace: (href: string) => void;
  back: () => void;
  basePath: string;
}

const RouterContext = createContext<RouterContextType | null>(null);

export function getBasePath(): string {
  if (typeof window === "undefined") return "/Hadron";
  const p = window.location.pathname;
  if (p.startsWith("/Hadron")) return "/Hadron";
  return "";
}

function normalizePath(fullPath: string, basePath: string): string {
  let path = fullPath;
  if (basePath && path.startsWith(basePath)) {
    path = path.slice(basePath.length);
  }
  if (!path.startsWith("/")) {
    path = "/" + path;
  }
  // Strip trailing slash except root
  if (path.length > 1 && path.endsWith("/")) {
    path = path.slice(0, -1);
  }
  return path || "/";
}

export function RouterProvider({ children }: { children: React.ReactNode }) {
  const basePath = useMemo(() => getBasePath(), []);

  // Handle SPA redirect query parameter (?p=... or ?/=...) from GitHub Pages 404.html
  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const spaPath = url.searchParams.get("p") || url.searchParams.get("/");
    if (spaPath) {
      url.searchParams.delete("p");
      url.searchParams.delete("/");
      const rawQuery = url.searchParams.toString().replace(/~and~/g, "&");
      const decodedPath = decodeURIComponent(spaPath);
      const targetUrl = `${basePath}${decodedPath.startsWith("/") ? decodedPath : "/" + decodedPath}${rawQuery ? "?" + rawQuery : ""}${url.hash}`;
      window.history.replaceState(null, "", targetUrl);
      setPathState(normalizePath(decodedPath, ""));
      setSearchState(new URLSearchParams(rawQuery));
    }
  }, [basePath]);

  const [pathState, setPathState] = useState<string>(() => {
    if (typeof window === "undefined") return "/";
    return normalizePath(window.location.pathname, basePath);
  });

  const [searchState, setSearchState] = useState<URLSearchParams>(() => {
    if (typeof window === "undefined") return new URLSearchParams();
    return new URLSearchParams(window.location.search);
  });

  const [paramsState, setParamsState] = useState<Record<string, string>>({});

  useEffect(() => {
    const handlePopState = () => {
      setPathState(normalizePath(window.location.pathname, basePath));
      setSearchState(new URLSearchParams(window.location.search));
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [basePath]);

  const push = useCallback((href: string) => {
    const [pathPart, queryPart] = href.split("?");
    const targetPath = normalizePath(pathPart, "");
    const fullHref = `${basePath}${targetPath}${queryPart ? "?" + queryPart : ""}`;
    window.history.pushState(null, "", fullHref);
    setPathState(targetPath);
    setSearchState(new URLSearchParams(queryPart || ""));
  }, [basePath]);

  const replace = useCallback((href: string) => {
    const [pathPart, queryPart] = href.split("?");
    const targetPath = normalizePath(pathPart, "");
    const fullHref = `${basePath}${targetPath}${queryPart ? "?" + queryPart : ""}`;
    window.history.replaceState(null, "", fullHref);
    setPathState(targetPath);
    setSearchState(new URLSearchParams(queryPart || ""));
  }, [basePath]);

  const back = useCallback(() => {
    window.history.back();
  }, []);

  const value = useMemo(() => ({
    pathname: pathState,
    searchParams: searchState,
    params: paramsState,
    push,
    replace,
    back,
    basePath,
  }), [pathState, searchState, paramsState, push, replace, back, basePath]);

  return (
    <RouterContext.Provider value={value}>
      <ParamsUpdater setParamsState={setParamsState} pathname={pathState} />
      {children}
    </RouterContext.Provider>
  );
}

function ParamsUpdater({
  setParamsState,
  pathname,
}: {
  setParamsState: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  pathname: string;
}) {
  useEffect(() => {
    const params: Record<string, string> = {};
    if (pathname.startsWith("/reviews/")) {
      const rest = pathname.slice("/reviews/".length);
      if (rest) params.id = decodeURIComponent(rest);
    } else if (pathname.startsWith("/hitl/")) {
      const rest = pathname.slice("/hitl/".length);
      if (rest) params.id = decodeURIComponent(rest);
    } else if (pathname.startsWith("/solutions/")) {
      const rest = pathname.slice("/solutions/".length);
      if (rest) params.framework = decodeURIComponent(rest);
    } else if (pathname.startsWith("/docs/")) {
      const rest = pathname.slice("/docs/".length);
      if (rest) params.slug = decodeURIComponent(rest);
    }
    setParamsState(params);
  }, [pathname, setParamsState]);
  return null;
}

export function useRouterContext(): RouterContextType {
  const ctx = useContext(RouterContext);
  if (!ctx) {
    return {
      pathname: "/",
      searchParams: new URLSearchParams(),
      params: {},
      push: (h) => { window.location.href = h; },
      replace: (h) => { window.location.replace(h); },
      back: () => { window.history.back(); },
      basePath: "",
    };
  }
  return ctx;
}
