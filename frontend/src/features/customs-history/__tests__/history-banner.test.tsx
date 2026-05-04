import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

import { HistoryBanner } from "../ui/history-banner";
import type { HistoryMatch } from "../model/types";

/**
 * Pure SSR rendering tests for HistoryBanner (Phase A Req 10).
 *
 * The frontend workspace has no jsdom configured (see other customs tests),
 * so we use `react-dom/server` to assert markup. Click interactions are
 * verified via localhost:3000 per `reference_localhost_browser_test.md`.
 */

function makeMatch(overrides: Partial<HistoryMatch> = {}): HistoryMatch {
  return {
    user_id: "user-123",
    user_email: "ivan@example.com",
    created_at: "2026-04-23T12:00:00Z",
    chosen_variants: {},
    manual_override: false,
    manual_rate_payload: null,
    is_actual: true,
    ...overrides,
  };
}

describe("HistoryBanner — actual choice (default tone)", () => {
  it("renders headline with DD.MM.YYYY date and email", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch()}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).toContain("Заполнено из истории от 23.04.2026");
    expect(html).toContain("ivan@example.com");
  });

  it("uses blue tinted card classes", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch()}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).toContain("border-blue-900");
    expect(html).toContain("bg-blue-950/20");
  });

  it("renders «Применить» button", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch()}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).toContain("Применить");
  });

  it("renders dismiss button with aria-label", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch()}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).toContain('aria-label="Скрыть подсказку"');
  });

  it("falls back to «пользователем» when user_email is null", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch({ user_email: null })}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).toContain("пользователем");
  });
});

describe("HistoryBanner — stale choice (warning tone)", () => {
  it("uses amber tinted card classes when is_actual=false", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch({ is_actual: false })}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).toContain("border-amber-900");
    expect(html).toContain("bg-amber-950/20");
  });

  it("renders alternate headline mentioning Alta variants change", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch({ is_actual: false })}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).toContain("Alta изменила варианты");
    expect(html).toContain("23.04.2026");
  });

  it("does NOT use blue card classes in warning mode", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch({ is_actual: false })}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).not.toContain("border-blue-900");
  });
});

describe("HistoryBanner — testid for parent integration", () => {
  it("exposes data-testid for the dialog parent to query", () => {
    const html = renderToString(
      <HistoryBanner
        suggestion={makeMatch()}
        onApply={() => {}}
        onDismiss={() => {}}
      />,
    );
    expect(html).toContain('data-testid="customs-history-banner"');
  });
});
