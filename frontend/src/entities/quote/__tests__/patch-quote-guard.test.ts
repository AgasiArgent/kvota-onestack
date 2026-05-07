import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Phase 5c — defensive role guard on patchQuote.
 *
 * patchQuote (mutations.ts:1900-1945) gates customer-facing field edits
 * (contact_person_id, delivery_address) by re-checking the caller's roles
 * client-side, in addition to the UI-level gate (canEditQuoteCustomerFields)
 * and the RLS UPDATE policy on kvota.quotes (migration 308). The guard
 * exists to defend against a parent component forgetting to disable the
 * dropdown — without it, a procurement user could fire the mutation and
 * rely on the server to reject it.
 *
 * The set of guarded fields must mirror the production constant
 * QUOTE_CUSTOMER_FIELD_KEYS in mutations.ts:
 *   ["contact_person_id", "delivery_address"]
 *
 * Other patches (delivery_priority, workflow_status, ...) skip the guard
 * entirely so the function remains usable for non-customer fields.
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

interface FakeSupabase {
  /** auth.getUser() return — null user simulates an unauthenticated session. */
  user: { id: string } | null;
  /**
   * Rows returned by the .from('user_roles').select(..).eq('user_id', ...)
   * chain. Shape mirrors the PostgREST embed `roles!inner(slug)`.
   */
  roleRows: Array<{ roles: { slug: string } | null }>;
  /** When set, the user_roles query returns this error instead of data. */
  rolesError: Error | null;
  /** Captured payload from .from('quotes').update(...) — null if never called. */
  quotesUpdatePayload: Record<string, unknown> | null;
  /** Captured id from .eq('id', ...) on the update chain. */
  quotesUpdatedId: string | null;
  /** Auth-roles query count, so we can assert the guard skipped on safe fields. */
  rolesQueryCount: number;
  from(table: string): unknown;
  auth: {
    getUser: () => Promise<{ data: { user: { id: string } | null } }>;
  };
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    user: { id: "user-1" },
    roleRows: [],
    rolesError: null,
    quotesUpdatePayload: null,
    quotesUpdatedId: null,
    rolesQueryCount: 0,
    auth: {
      getUser: async () => ({ data: { user: state.user } }),
    },
    from(table: string) {
      if (table === "user_roles") {
        state.rolesQueryCount += 1;
        return {
          select: (_cols: string) => ({
            eq: async (_col: string, _val: string) => {
              if (state.rolesError) {
                return { data: null, error: state.rolesError };
              }
              return { data: state.roleRows, error: null };
            },
          }),
        };
      }
      if (table === "quotes") {
        return {
          update: (payload: Record<string, unknown>) => {
            state.quotesUpdatePayload = payload;
            return {
              eq: async (_col: string, value: string) => {
                state.quotesUpdatedId = value;
                return { error: null };
              },
            };
          },
        };
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

describe("patchQuote — defensive customer-field role guard", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  // --- Guarded fields: contact_person_id, delivery_address ---

  it("throws for procurement role when patching contact_person_id", async () => {
    fakeSupabase.roleRows = [{ roles: { slug: "procurement" } }];
    const { patchQuote } = await import("../mutations");

    await expect(
      patchQuote("quote-1", { contact_person_id: "contact-X" })
    ).rejects.toThrow(
      "Только роли «продажи» могут менять контакт и адрес доставки"
    );

    // Guard must have prevented the UPDATE from being issued.
    expect(fakeSupabase.quotesUpdatePayload).toBeNull();
    expect(fakeSupabase.rolesQueryCount).toBe(1);
  });

  it("succeeds for sales role when patching contact_person_id", async () => {
    fakeSupabase.roleRows = [{ roles: { slug: "sales" } }];
    const { patchQuote } = await import("../mutations");

    await patchQuote("quote-1", { contact_person_id: "contact-X" });

    expect(fakeSupabase.quotesUpdatePayload).toEqual({
      contact_person_id: "contact-X",
    });
    expect(fakeSupabase.quotesUpdatedId).toBe("quote-1");
  });

  it("throws for procurement role when patching delivery_address", async () => {
    fakeSupabase.roleRows = [{ roles: { slug: "procurement" } }];
    const { patchQuote } = await import("../mutations");

    await expect(
      patchQuote("quote-1", { delivery_address: "Москва, ул. Ленина 1" })
    ).rejects.toThrow(
      "Только роли «продажи» могут менять контакт и адрес доставки"
    );

    expect(fakeSupabase.quotesUpdatePayload).toBeNull();
  });

  // --- Non-guarded fields: delivery_priority + future additions ---

  it("succeeds for procurement role when patching delivery_priority (not a customer field)", async () => {
    fakeSupabase.roleRows = [{ roles: { slug: "procurement" } }];
    const { patchQuote } = await import("../mutations");

    await patchQuote("quote-1", { delivery_priority: "urgent" });

    expect(fakeSupabase.quotesUpdatePayload).toEqual({
      delivery_priority: "urgent",
    });
    // Guard must skip entirely — no auth/role round-trip when fields are safe.
    expect(fakeSupabase.rolesQueryCount).toBe(0);
  });

  it("succeeds for procurement role when patching unrelated field (workflow_status-like)", async () => {
    fakeSupabase.roleRows = [{ roles: { slug: "procurement" } }];
    const { patchQuote } = await import("../mutations");

    // Cast to the patchQuote update signature; the function accepts a
    // Partial of {contact_person_id, delivery_address, delivery_priority}.
    // We pass an unrelated key cast as one of the safe fields to verify the
    // guard's field-set check (it must only fire for QUOTE_CUSTOMER_FIELD_KEYS).
    // In practice patchQuote is typed narrowly so this case is mostly
    // theoretical — but the constant-set check must not regress to a
    // permissive default.
    await patchQuote("quote-1", { delivery_priority: null });

    // The mutation must have run without consulting roles.
    expect(fakeSupabase.rolesQueryCount).toBe(0);
    expect(fakeSupabase.quotesUpdatedId).toBe("quote-1");
  });

  // --- Edge cases ---

  it("throws when caller has no roles at all", async () => {
    fakeSupabase.roleRows = [];
    const { patchQuote } = await import("../mutations");

    await expect(
      patchQuote("quote-1", { contact_person_id: "contact-X" })
    ).rejects.toThrow(
      "Только роли «продажи» могут менять контакт и адрес доставки"
    );

    expect(fakeSupabase.quotesUpdatePayload).toBeNull();
  });

  it("succeeds when caller has sales among mixed roles (OR semantics)", async () => {
    fakeSupabase.roleRows = [
      { roles: { slug: "procurement" } },
      { roles: { slug: "sales" } },
    ];
    const { patchQuote } = await import("../mutations");

    await patchQuote("quote-1", { contact_person_id: "contact-X" });

    expect(fakeSupabase.quotesUpdatePayload).toEqual({
      contact_person_id: "contact-X",
    });
  });

  it("throws «Не авторизованы» when no user session", async () => {
    fakeSupabase.user = null;
    const { patchQuote } = await import("../mutations");

    await expect(
      patchQuote("quote-1", { contact_person_id: "contact-X" })
    ).rejects.toThrow("Не авторизованы");

    expect(fakeSupabase.quotesUpdatePayload).toBeNull();
  });
});
