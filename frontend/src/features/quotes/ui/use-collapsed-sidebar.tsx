"use client";

import { useEffect } from "react";

/**
 * Collapses the sidebar when mounted, restores on unmount.
 * Used on quote detail page to give more horizontal space for Handsontable grids.
 */
export function UseCollapsedSidebar() {
  useEffect(() => {
    const prev = document.documentElement.getAttribute("data-sidebar-collapsed");
    document.documentElement.setAttribute("data-sidebar-collapsed", "true");

    return () => {
      document.documentElement.setAttribute(
        "data-sidebar-collapsed",
        prev ?? "false"
      );
    };
  }, []);

  return null;
}
