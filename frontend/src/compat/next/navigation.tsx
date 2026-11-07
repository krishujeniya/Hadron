import { useMemo } from "react";
import { useRouterContext } from "./router-context";

export function useRouter() {
  const ctx = useRouterContext();
  return useMemo(() => ({
    push: ctx.push,
    replace: ctx.replace,
    back: ctx.back,
    forward: () => window.history.forward(),
    refresh: () => window.location.reload(),
    prefetch: () => {},
  }), [ctx.push, ctx.replace, ctx.back]);
}

export function usePathname(): string {
  const ctx = useRouterContext();
  return ctx.pathname;
}

export function useSearchParams(): URLSearchParams {
  const ctx = useRouterContext();
  return ctx.searchParams;
}

export function useParams<T extends Record<string, string | string[]> = Record<string, string>>(): T {
  const ctx = useRouterContext();
  return ctx.params as T;
}

export function notFound(): never {
  throw new Error("NEXT_NOT_FOUND");
}
