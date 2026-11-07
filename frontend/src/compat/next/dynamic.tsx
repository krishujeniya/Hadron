import React, { ComponentType, lazy, Suspense } from "react";

interface DynamicOptions {
  ssr?: boolean;
  loading?: () => React.ReactNode;
}

export default function dynamic<P extends object>(
  dynamicOptions: () => Promise<{ default: ComponentType<P> } | ComponentType<P>>,
  options?: DynamicOptions
): ComponentType<P> {
  const LazyComponent = lazy(async () => {
    const mod = await dynamicOptions();
    if ("default" in mod) {
      return { default: mod.default };
    }
    return { default: mod };
  });

  const Loading = options?.loading || (() => null);

  return function DynamicWrapper(props: P) {
    return (
      <Suspense fallback={<Loading />}>
        {React.createElement(LazyComponent as unknown as ComponentType<P>, props as React.Attributes & P)}
      </Suspense>
    );
  };
}
