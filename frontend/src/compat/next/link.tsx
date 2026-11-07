import React from "react";
import { useRouterContext } from "./router-context";

export interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  href: string;
  replace?: boolean;
  scroll?: boolean;
  prefetch?: boolean;
  children?: React.ReactNode;
}

export default function Link({
  href,
  replace = false,
  scroll = true,
  prefetch,
  children,
  onClick,
  className,
  ...props
}: LinkProps) {
  const router = useRouterContext();

  const isExternal =
    href.startsWith("http://") ||
    href.startsWith("https://") ||
    href.startsWith("//") ||
    href.startsWith("mailto:") ||
    href.startsWith("tel:");

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (onClick) onClick(e);
    if (
      e.defaultPrevented ||
      isExternal ||
      e.button !== 0 ||
      e.metaKey ||
      e.altKey ||
      e.ctrlKey ||
      e.shiftKey
    ) {
      return;
    }

    e.preventDefault();
    if (replace) {
      router.replace(href);
    } else {
      router.push(href);
    }

    if (scroll && typeof window !== "undefined") {
      window.scrollTo(0, 0);
    }
  };

  const resolvedHref = isExternal
    ? href
    : `${router.basePath}${href.startsWith("/") ? href : "/" + href}`;

  return (
    <a href={resolvedHref} onClick={handleClick} className={className} {...props}>
      {children}
    </a>
  );
}
