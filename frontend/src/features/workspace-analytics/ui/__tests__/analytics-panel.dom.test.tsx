// @vitest-environment jsdom
/**
 * Track E (Sprint 2026-05-07) — «Производительность логистов» rendered the
 * truncated UUID prefix `96d797ee` in the «Логист» column instead of the
 * user's display name.
 *
 * Root cause: `api/workspace.py::_resolve_user_names` consulted only
 * ``auth.users.user_metadata`` and fell back to ``str(uid)[:8]`` for users
 * whose metadata was empty. The canonical full_name lives in
 * ``kvota.user_profiles.full_name`` (see api/notes.py for the project-wide
 * pattern). The Python fix queries user_profiles first; this defensive
 * frontend fallback covers any residual leak by mapping empty / UUID-shaped
 * names to a localized «— Неизвестный логист» label.
 *
 * Tests pin three contracts:
 *   1. A real full_name renders verbatim.
 *   2. An empty user_name renders the localized fallback (never blank).
 *   3. An 8-char hex UUID prefix that slipped through (e.g. `96d797ee`)
 *      renders the localized fallback — never the bare UUID slice.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { AnalyticsPanel } from "../analytics-panel";
import type { WorkspaceAnalyticsRow } from "../../api/server-queries";

afterEach(() => {
  cleanup();
});

const baseRow: WorkspaceAnalyticsRow = {
  user_id: "11111111-1111-4111-8111-111111111111",
  user_name: "Иванов Иван Иванович",
  completed_count: 7,
  median_hours: 6.4,
  on_time_count: 5,
  on_time_pct: 71,
};

describe("AnalyticsPanel — Логист column display name", () => {
  it("renders the full_name verbatim when present", () => {
    render(<AnalyticsPanel domain="logistics" rows={[baseRow]} />);
    expect(screen.getByText("Иванов Иван Иванович")).toBeTruthy();
    // Sanity: never leak the raw UUID anywhere in the row.
    expect(screen.queryByText("11111111")).toBeNull();
  });

  it("falls back to «— Неизвестный логист» when user_name is empty", () => {
    const row: WorkspaceAnalyticsRow = { ...baseRow, user_name: "" };
    render(<AnalyticsPanel domain="logistics" rows={[row]} />);
    expect(screen.getByText("— Неизвестный логист")).toBeTruthy();
  });

  it("falls back to «— Неизвестный логист» on UUID-prefix leak (96d797ee)", () => {
    // This mirrors the exact regression captured in /tmp/repro-2026-05-07.md:
    // a stale 8-char hex slice should never reach the user.
    const row: WorkspaceAnalyticsRow = { ...baseRow, user_name: "96d797ee" };
    render(<AnalyticsPanel domain="logistics" rows={[row]} />);
    expect(screen.getByText("— Неизвестный логист")).toBeTruthy();
    expect(screen.queryByText("96d797ee")).toBeNull();
  });

  it("renders the empty-state copy when there are no rows", () => {
    render(<AnalyticsPanel domain="logistics" rows={[]} />);
    expect(screen.getByText("Нет данных для отображения")).toBeTruthy();
  });
});
