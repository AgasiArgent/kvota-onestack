"use client";

import { useEffect } from "react";

/**
 * Auto-collapses sidebar on mount via custom event, restores on unmount.
 * The sidebar component listens for 'sidebar-force-collapse' events.
 */
export function UseCollapsedSidebar() {
  useEffect(() => {
    window.dispatchEvent(new CustomEvent("sidebar-force-collapse", { detail: true }));

    return () => {
      window.dispatchEvent(new CustomEvent("sidebar-force-collapse", { detail: false }));
    };
  }, []);

  return null;
}
