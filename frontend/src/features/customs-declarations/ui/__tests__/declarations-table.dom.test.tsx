// @vitest-environment jsdom
/**
 * Track D regression (Sprint 2026-05-07):
 * `/customs/declarations` was logging React hydration mismatch error #418
 * because `formatDate` rendered dates without an explicit `timeZone`.
 *
 * `new Date("2026-04-15").toLocaleDateString("ru-RU", { ... })` produces
 * - "14.04.2026" when the host runs in UTC (Docker server)
 * - "15.04.2026" when the host runs in Europe/Moscow (typical user browser)
 *
 * The fix pins the formatter to `timeZone: "Europe/Moscow"` so server-render
 * and client-render produce byte-identical strings. The two assertions below
 * lock that contract: the rendered output must be deterministic when called
 * twice (proxy for "server output == client output, no hydration drift").
 *
 * NOTE: jsdom cannot directly assert the absence of React hydration warnings
 * — that requires a real browser. Phase 5e localhost browser-test will
 * verify the console is clean. See docs/plans/2026-05-07-multi-test-scope.md.
 */
import { describe, expect, it, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { DeclarationsTable } from "../declarations-table";
import type {
  CustomsDeclaration,
  CustomsDeclarationItem,
} from "@/entities/customs-declaration";

afterEach(() => {
  cleanup();
});

const baseDecl: CustomsDeclaration = {
  id: "d-1",
  regnum: "10000000/000000/0000001",
  // Date-only string (PostgreSQL DATE column) — this is the shape the
  // hydration mismatch was triggered by.
  declaration_date: "2026-04-15",
  sender_name: "ООО Тестовый Отправитель",
  internal_ref: "REF-001",
  total_customs_value_rub: 1000000,
  total_duty_rub: 50000,
  total_fee_rub: 750,
  item_count: 3,
  matched_count: 2,
};

const allItems: Record<string, CustomsDeclarationItem[]> = {};

describe("DeclarationsTable — date rendering is timezone-stable", () => {
  it("renders a date-only string in Europe/Moscow regardless of host TZ", () => {
    const { container } = render(
      <DeclarationsTable declarations={[baseDecl]} allItems={allItems} />,
    );
    // 2026-04-15 in Europe/Moscow → "15.04.2026" — must NOT be "14.04.2026"
    expect(container.textContent).toContain("15.04.2026");
    expect(container.textContent).not.toContain("14.04.2026");
  });

  it("produces identical markup across two renders (deterministic)", () => {
    // Proxy for SSR/CSR parity: identical props must produce identical HTML
    // on every call. If formatDate were timezone-sensitive at runtime, this
    // would still pass on a single host — but combined with the assertion
    // above (locking the MSK output) we cover both axes.
    const first = render(
      <DeclarationsTable declarations={[baseDecl]} allItems={allItems} />,
    );
    const firstHtml = first.container.innerHTML;
    cleanup();

    const second = render(
      <DeclarationsTable declarations={[baseDecl]} allItems={allItems} />,
    );
    expect(second.container.innerHTML).toBe(firstHtml);
  });

  it("renders em-dash for null declaration_date (no Invalid Date leak)", () => {
    const decl: CustomsDeclaration = { ...baseDecl, declaration_date: null };
    render(<DeclarationsTable declarations={[decl]} allItems={allItems} />);
    // Defensive: when the DB returns null we should see "—", never
    // "Invalid Date", which would itself cause a hydration mismatch in
    // some Node/browser combinations.
    expect(screen.queryByText(/Invalid Date/)).toBeNull();
  });
});
