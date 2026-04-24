import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";
import { extractErrorMessage } from "@/shared/lib/errors";

/**
 * CRITICAL #1 (PR #73 fix-up) — TabOverview error-path SSR sanity.
 *
 * Previously the save `catch` only did `console.error` with no toast, so
 * users saw the edit dialog stay open with no feedback on RLS/validation
 * failures. Fix adds a toast.error() call using extractErrorMessage, keeping
 * the finally { setSaving(false) } so the user can retry.
 *
 * Same framework constraint as the other modal tests: vitest has no DOM
 * harness, so we verify module loads, renders in view-mode without throwing,
 * and separately that the extractErrorMessage path (imported in the file)
 * returns the Russian fallback for unknown error shapes.
 */

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: () => {},
    push: () => {},
    replace: () => {},
    back: () => {},
    forward: () => {},
    prefetch: () => {},
  }),
}));

vi.mock("@/entities/supplier/mutations", () => ({
  updateSupplier: vi.fn(async () => undefined),
}));

import type { SupplierDetail } from "@/entities/supplier/types";
import { TabOverview } from "../tab-overview";

function makeSupplier(overrides: Partial<SupplierDetail> = {}): SupplierDetail {
  return {
    id: "s-1",
    organization_id: "org-1",
    name: "Acme GmbH",
    supplier_code: "ACME",
    country: "Германия",
    country_code: "DE",
    city: "Berlin",
    registration_number: "DE123456789",
    default_payment_terms: "30 дней",
    notes: null,
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
    updated_at: null,
    ...overrides,
  };
}

describe("TabOverview — module + render (SSR sanity)", () => {
  it("exports as a function", () => {
    expect(typeof TabOverview).toBe("function");
  });

  it("renders without throwing in view mode", () => {
    const html = renderToString(<TabOverview supplier={makeSupplier()} />);
    expect(typeof html).toBe("string");
    expect(html).toContain("Acme GmbH");
  });

  it("renders the edit affordance in view mode", () => {
    const html = renderToString(<TabOverview supplier={makeSupplier()} />);
    // The outline "Редактировать" button is visible in view mode.
    expect(html).toContain("Редактировать");
  });
});

describe("TabOverview — error-path helper integration", () => {
  // The handleSave catch block runs extractErrorMessage(err) with a Russian
  // fallback. These assertions confirm the helper behavior matches the
  // copy used in the component.
  it("extracts Postgrest RLS message", () => {
    const rlsErr = {
      code: "42501",
      message: "permission denied for table suppliers",
    };
    expect(extractErrorMessage(rlsErr)).toBe(
      "permission denied for table suppliers",
    );
  });

  it("falls back to null for error shapes without a usable message", () => {
    // The component then uses "Не удалось сохранить поставщика" as fallback.
    expect(extractErrorMessage({ foo: "bar" })).toBeNull();
  });
});
