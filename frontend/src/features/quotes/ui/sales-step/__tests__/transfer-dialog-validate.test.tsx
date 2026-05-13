import { describe, it, expect } from "vitest";

import { validateForTransfer } from "../transfer-dialog";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";

/**
 * Testing 2 row 23 (МОП/РОП): the customer contact must be filled before a
 * МОП can hand the quote off from «Заявка» → «Закупки». The gate lives in
 * `validateForTransfer`, which feeds the «Передать в закупки» button's
 * disabled-state + tooltip in `TransferDialog`.
 *
 * Pure-function tests — no DOM, no mocks. The companion .dom-test for the
 * panel covers field highlighting via `data-field="contact_person_id"`.
 */

function makeQuote(overrides: Partial<QuoteDetailRow> = {}): QuoteDetailRow {
  // Cast: QuoteDetailRow is an inferred Supabase-derived type with ~100
  // columns; we only need a handful for this validator. Construct a minimal
  // object and assert the cast — matches the pattern in
  // calculation-action-bar tests / sales-items-table tests where the row
  // type is filled selectively.
  return {
    id: "q-1",
    customer_id: "c-1",
    contact_person_id: "cc-1",
    seller_company_id: "s-1",
    delivery_city: "Москва",
    delivery_country: "Россия",
    delivery_method: "Авто",
    incoterms: "DAP",
    ...overrides,
  } as unknown as QuoteDetailRow;
}

function makeItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  return {
    id: "qi-1",
    product_name: "Болт М8",
    quantity: 10,
    unit: "шт",
    ...overrides,
  } as unknown as QuoteItemRow;
}

describe("validateForTransfer — customer contact gate (Testing 2 row 23)", () => {
  it("returns no errors when every required field (incl. contact_person_id) is set", () => {
    const result = validateForTransfer(makeQuote(), [makeItem()]);
    expect(result.errors).toEqual([]);
    expect(result.missingFields).toEqual([]);
  });

  it("blocks transfer with «Контакт клиента» error when contact_person_id is null", () => {
    const result = validateForTransfer(
      makeQuote({ contact_person_id: null }),
      [makeItem()],
    );
    expect(result.missingFields).toContain("contact_person_id");
    expect(result.errors).toContain("Контакт клиента");
  });

  it("blocks transfer when contact_person_id is undefined (legacy quotes before column existed)", () => {
    const quote = makeQuote();
    // Force the field off entirely to exercise the !value path
    delete (quote as Record<string, unknown>).contact_person_id;

    const result = validateForTransfer(quote, [makeItem()]);
    expect(result.missingFields).toContain("contact_person_id");
    expect(result.errors).toContain("Контакт клиента");
  });

  it("blocks transfer when contact_person_id is an empty string (defensive — DB stores null but form state may emit '')", () => {
    const result = validateForTransfer(
      makeQuote({ contact_person_id: "" as unknown as string }),
      [makeItem()],
    );
    expect(result.missingFields).toContain("contact_person_id");
    expect(result.errors).toContain("Контакт клиента");
  });

  it("reports contact_person_id alongside other empty fields rather than short-circuiting", () => {
    const result = validateForTransfer(
      makeQuote({ contact_person_id: null, seller_company_id: null }),
      [makeItem()],
    );
    expect(result.missingFields).toEqual(
      expect.arrayContaining(["contact_person_id", "seller_company_id"]),
    );
    expect(result.errors).toEqual(
      expect.arrayContaining(["Контакт клиента", "Продавец"]),
    );
  });
});
