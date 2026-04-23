"use client";

/**
 * TanStack Query provider — root wrapper for every client-side query in the app.
 *
 * Holds a single {@link QueryClient} in state so React's double-render in
 * strict mode does not create two independent caches. Defaults are tuned for
 * Kvota's read patterns (journey canvas, dashboards) — data is considered
 * fresh for 30 s and garbage-collected 5 min after the last subscriber
 * unmounts. Requests retry once to shrug off transient network blips without
 * hammering the Python API on sustained outages.
 *
 * Devtools are intentionally **not** bundled — keep the production payload
 * lean; re-add them ad-hoc if/when the team needs them.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            retry: 1,
          },
        },
      })
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
