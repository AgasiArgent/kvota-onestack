import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";
import { extractErrorMessage } from "@/shared/lib/errors";

/**
 * CRITICAL #3 (PR #73 fix-up) — CreateSupplierDialog error-path hardening.
 *
 * Prior catch branched on `raw.includes("row-level security") | "unique" |
 * "duplicate"` with no `console.error` of the original error, so failures
 * were both undebuggable and fragile to PG error text drift. Fix:
 *   1. prepend `console.error` for traceability
 *   2. keep the RU "Нет прав" / "Уже существует" niceties where they match
 *   3. replace the generic final fallback with extractErrorMessage(err)
 *      ?? "Не удалось создать поставщика"
 *   4. fix `React.SubmitEvent<HTMLFormElement>` typo → `React.FormEvent<...>`
 *
 * Same SSR caveat as other modal tests — we verify module loads and renders
 * in its closed state without throwing, and separately assert the helper
 * behavior the component now relies on.
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
  createSupplier: vi.fn(async () => ({ id: "s-new" })),
}));

import { CreateSupplierDialog } from "../create-supplier-dialog";

describe("CreateSupplierDialog — module + closed-state (SSR sanity)", () => {
  it("exports as a function", () => {
    expect(typeof CreateSupplierDialog).toBe("function");
  });

  it("renders without throwing when open=false", () => {
    const html = renderToString(
      <CreateSupplierDialog
        orgId="org-1"
        open={false}
        onOpenChange={() => {}}
      />,
    );
    expect(typeof html).toBe("string");
  });
});

/**
 * The handleSubmit catch block runs:
 *   1. console.error (traceability)
 *   2. raw.includes("row-level security") → "Нет прав"
 *   3. raw.includes("unique"|"duplicate") → "Уже существует"
 *   4. else → extractErrorMessage(err) ?? "Не удалось создать поставщика"
 *
 * The RU-nicety branches (2+3) are fragile to PG text changes but stay as
 * UX for the common cases. These tests verify the fallback chain (4) which
 * is the bug-fix contract — no more generic "Ошибка создания поставщика"
 * when a richer message is available.
 */
describe("CreateSupplierDialog — error-path fallback chain", () => {
  it("extracts Postgrest validation message (unique violation with details)", () => {
    const err = {
      code: "23505",
      message: "duplicate key value violates unique constraint",
      details: "Key (name)=(Acme GmbH) already exists.",
    };
    expect(extractErrorMessage(err)).toBe(
      "duplicate key value violates unique constraint (Key (name)=(Acme GmbH) already exists.)",
    );
  });

  it("extracts native Error message", () => {
    const err = new Error("Network request failed");
    expect(extractErrorMessage(err)).toBe("Network request failed");
  });

  it("returns null for unknown error shapes so component uses RU fallback", () => {
    // Component pattern: extractErrorMessage(err) ?? "Не удалось создать поставщика"
    // Confirms the `??` branch fires for these values.
    expect(extractErrorMessage(null)).toBeNull();
    expect(extractErrorMessage(undefined)).toBeNull();
    expect(extractErrorMessage({})).toBeNull();
  });
});
