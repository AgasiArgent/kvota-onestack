"use client";

/**
 * JourneyDrawer — the right-hand panel of /journey.
 *
 * Opens when a node is selected on the canvas (URL `?node=...`). Displays —
 * read-only in Task 18 — every field about the node in the order mandated
 * by Req 5.1:
 *
 *   header → roles → stories → status → screenshot → feedback →
 *   training → pin list → history expander
 *
 * Ghost nodes hide Screenshot + Pin List (Req 5.2) — those sections only
 * make sense for shipped routes.
 *
 * Status editing (Req 5.5, 6.1) lands in Task 19. This file keeps the
 * status section read-only by rendering badges, not form controls.
 *
 * Keyboard: Esc closes the drawer (Req 5.6). The Esc handler is exported
 * as a pure helper (`makeEscapeHandler`) so it can be unit-tested without
 * a DOM — the frontend workspace has no jsdom / happy-dom.
 *
 * Slide-in animation: the panel is always mounted in the DOM (when open);
 * the entrance uses a constrained `transition-transform` on the X axis —
 * NOT `transition: all`, NOT a `translateY` bounce (design-system.md rule).
 */

import { useEffect } from "react";
import { useNodeDetail } from "@/entities/journey";
import type { JourneyNodeDetail, JourneyNodeId } from "@/entities/journey";

import { DrawerHeader } from "./drawer-header";
import { RolesSection } from "./roles-section";
import { StoriesSection } from "./stories-section";
import { StatusSection } from "./status-section";
import { ScreenshotSection } from "./screenshot-section";
import { FeedbackSection } from "./feedback-section";
import { TrainingSection } from "./training-section";
import { PinListSection } from "./pin-list-section";
import { HistoryExpander } from "./history-expander";

// ---------------------------------------------------------------------------
// Testids — centralised so tests don't drift from component renders.
// ---------------------------------------------------------------------------

export const DRAWER_TESTIDS = {
  panel: "journey-drawer-panel",
  header: "drawer-header",
  roles: "roles-section",
  stories: "stories-section",
  status: "status-section",
  screenshot: "screenshot-section",
  feedback: "feedback-section",
  training: "training-section",
  pinList: "pin-list-section",
  historyExpander: "history-expander",
  loading: "drawer-loading",
  error: "drawer-error",
} as const;

// ---------------------------------------------------------------------------
// Pure helpers (exported for unit tests)
// ---------------------------------------------------------------------------

export function isGhostDetail(detail: JourneyNodeDetail): boolean {
  return detail.ghost_status !== null;
}

export function shouldShowScreenshot(detail: JourneyNodeDetail): boolean {
  return !isGhostDetail(detail);
}

export function shouldShowPinList(detail: JourneyNodeDetail): boolean {
  return !isGhostDetail(detail);
}

export function makeEscapeHandler(
  onClose: () => void
): (e: KeyboardEvent) => void {
  return (e: KeyboardEvent) => {
    if (e.key === "Escape") onClose();
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface JourneyDrawerProps {
  readonly nodeId: JourneyNodeId | null;
  readonly onClose: () => void;
}

export function JourneyDrawer({ nodeId, onClose }: JourneyDrawerProps) {
  // `useNodeDetail` requires a non-empty string. We pass `""` when the drawer
  // is closed; it's fine because we early-return before touching `data`.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const query = useNodeDetail((nodeId ?? "") as any);

  useEffect(() => {
    if (!nodeId) return;
    const handler = makeEscapeHandler(onClose);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [nodeId, onClose]);

  if (!nodeId) return null;

  const panelClasses =
    "w-[400px] shrink-0 border-l border-border-light bg-sidebar overflow-y-auto " +
    "transition-transform duration-200 ease-out translate-x-0";

  return (
    <aside
      data-testid={DRAWER_TESTIDS.panel}
      role="complementary"
      aria-label="Подробности узла"
      className={panelClasses}
    >
      {query.isLoading && (
        <div
          data-testid={DRAWER_TESTIDS.loading}
          className="p-4 text-sm text-text-muted"
        >
          Загрузка…
        </div>
      )}

      {query.isError && (
        <div
          data-testid={DRAWER_TESTIDS.error}
          className="p-4 text-sm text-destructive"
          role="alert"
        >
          Не удалось загрузить данные узла.
        </div>
      )}

      {query.data && (
        <DrawerBody detail={query.data} onClose={onClose} />
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Body — split so we can narrow `detail` once and share section logic.
// ---------------------------------------------------------------------------

function DrawerBody({
  detail,
  onClose,
}: {
  detail: JourneyNodeDetail;
  onClose: () => void;
}) {
  return (
    <div className="flex flex-col divide-y divide-border-light">
      <DrawerHeader detail={detail} onClose={onClose} />
      <RolesSection detail={detail} />
      <StoriesSection detail={detail} />
      <StatusSection detail={detail} />
      {shouldShowScreenshot(detail) && <ScreenshotSection detail={detail} />}
      <FeedbackSection detail={detail} />
      <TrainingSection detail={detail} />
      {shouldShowPinList(detail) && <PinListSection detail={detail} />}
      <HistoryExpander nodeId={detail.node_id} />
    </div>
  );
}
