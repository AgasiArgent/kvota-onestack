/**
 * Testing 2 row 61 — Server-action unit tests for
 * `updateDistributionComment`.
 *
 * The action partially patches `kvota.quotes.sales_checklist` JSONB without
 * disturbing the rest of the checklist payload. These tests pin:
 *   - Read-modify-write preserves sibling JSONB keys.
 *   - Role gating: only admin / sales / head_of_sales may write.
 *   - Whitespace-only input is normalised to `null` (matches the back-end
 *     submit-procurement normalisation in `api/quotes.py`).
 *   - Empty / null input becomes `null` in the JSONB payload.
 *   - Auth failures bail out without touching the DB.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

// ---------------------------------------------------------------------------
// Fake Supabase admin client + getSessionUser
// ---------------------------------------------------------------------------

interface FakeSupabase {
  /** Row returned by .from('quotes').select('sales_checklist').eq().maybeSingle(). */
  existingChecklist: Record<string, unknown> | null;
  /** Captured payload from .from('quotes').update(...). */
  updatePayload: Record<string, unknown> | null;
  /** Set when the update should report an error. */
  updateError: Error | null;
  /** Set when the read should report an error. */
  readError: Error | null;
  /** Per-eq() calls captured for assertion. */
  updateEqCalls: Array<[string, unknown]>;
  readEqCalls: Array<[string, unknown]>;
  from: (table: string) => unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    existingChecklist: null,
    updatePayload: null,
    updateError: null,
    readError: null,
    updateEqCalls: [],
    readEqCalls: [],
    from(table: string) {
      if (table !== "quotes") {
        throw new Error(`Unexpected table: ${table}`);
      }
      return {
        select: () => {
          // Read-modify-write chain: .select().eq().eq().maybeSingle()
          const chain: Record<string, unknown> = {
            eq(col: string, val: unknown) {
              state.readEqCalls.push([col, val]);
              return chain;
            },
            maybeSingle: async () => {
              if (state.readError) return { data: null, error: state.readError };
              return {
                data:
                  state.existingChecklist !== null
                    ? { sales_checklist: state.existingChecklist }
                    : state.readEqCalls.length === 0
                      ? null
                      : { sales_checklist: null },
                error: null,
              };
            },
          };
          return chain;
        },
        update(payload: Record<string, unknown>) {
          state.updatePayload = payload;
          const chain: Record<string, unknown> = {
            eq(col: string, val: unknown) {
              state.updateEqCalls.push([col, val]);
              return state.updateEqCalls.length === 2
                ? Promise.resolve({ error: state.updateError })
                : chain;
            },
          };
          return chain;
        },
      };
    },
  };
  return state;
}

// ---------------------------------------------------------------------------
// Mocked modules — must be set up BEFORE importing server-actions
// ---------------------------------------------------------------------------

interface FakeSession {
  id: string;
  orgId: string | null;
  roles: string[];
}
let fakeSession: FakeSession | null = null;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: () => fakeSupabase,
  createAdminClient: () => fakeSupabase,
}));

vi.mock("@/entities/user", () => ({
  getSessionUser: async () => fakeSession,
}));

vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
}));

// Import after mocks so the server-actions module picks them up.
const { updateDistributionComment } = await import("../server-actions");

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("updateDistributionComment — role gating", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["sales"] };
  });

  it("permits writes for sales", async () => {
    fakeSupabase.existingChecklist = { equipment_description: "X" };
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(true);
    expect(fakeSupabase.updatePayload).not.toBeNull();
  });

  it("permits writes for head_of_sales", async () => {
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["head_of_sales"] };
    fakeSupabase.existingChecklist = {};
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(true);
  });

  it("permits writes for admin", async () => {
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["admin"] };
    fakeSupabase.existingChecklist = {};
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(true);
  });

  it("rejects writes for procurement", async () => {
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["procurement"] };
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Not authorized");
    expect(fakeSupabase.updatePayload).toBeNull();
  });

  it.each([
    ["logistics"],
    ["customs"],
    ["head_of_procurement"],
    ["head_of_logistics"],
    ["finance"],
  ])("rejects writes for %s", async (role) => {
    fakeSession = { id: "u-1", orgId: "org-1", roles: [role] };
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(false);
    expect(fakeSupabase.updatePayload).toBeNull();
  });

  it("rejects writes when not authenticated", async () => {
    fakeSession = null;
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Not authenticated");
  });

  it("rejects writes when session has no orgId", async () => {
    fakeSession = { id: "u-1", orgId: null, roles: ["sales"] };
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Not authenticated");
  });
});

describe("updateDistributionComment — JSONB partial update", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["sales"] };
  });

  it("preserves sibling fields when patching distribution_comment", async () => {
    fakeSupabase.existingChecklist = {
      is_estimate: true,
      is_tender: false,
      direct_request: false,
      trading_org_request: true,
      equipment_description: "Сервер DL380",
      distribution_comment: "Старый комментарий",
      completed_at: "2026-05-01T10:00:00Z",
      completed_by: "u-mop",
    };

    const res = await updateDistributionComment("q-1", "Новый комментарий");

    expect(res).toEqual({ success: true, value: "Новый комментарий" });
    expect(fakeSupabase.updatePayload?.sales_checklist).toEqual({
      is_estimate: true,
      is_tender: false,
      direct_request: false,
      trading_org_request: true,
      equipment_description: "Сервер DL380",
      distribution_comment: "Новый комментарий",
      completed_at: "2026-05-01T10:00:00Z",
      completed_by: "u-mop",
    });
  });

  it("trims surrounding whitespace from the comment", async () => {
    fakeSupabase.existingChecklist = {};
    const res = await updateDistributionComment("q-1", "  Срочно к Алейне  ");
    expect(res.value).toBe("Срочно к Алейне");
    expect(
      (fakeSupabase.updatePayload?.sales_checklist as Record<string, unknown>)
        .distribution_comment,
    ).toBe("Срочно к Алейне");
  });

  it("normalises whitespace-only input to null", async () => {
    fakeSupabase.existingChecklist = {
      equipment_description: "X",
      distribution_comment: "old",
    };
    const res = await updateDistributionComment("q-1", "   ");
    expect(res.value).toBeNull();
    expect(
      (fakeSupabase.updatePayload?.sales_checklist as Record<string, unknown>)
        .distribution_comment,
    ).toBeNull();
  });

  it("normalises empty string to null", async () => {
    fakeSupabase.existingChecklist = {};
    const res = await updateDistributionComment("q-1", "");
    expect(res.value).toBeNull();
    expect(
      (fakeSupabase.updatePayload?.sales_checklist as Record<string, unknown>)
        .distribution_comment,
    ).toBeNull();
  });

  it("normalises explicit null to null", async () => {
    fakeSupabase.existingChecklist = {};
    const res = await updateDistributionComment("q-1", null);
    expect(res.value).toBeNull();
    expect(
      (fakeSupabase.updatePayload?.sales_checklist as Record<string, unknown>)
        .distribution_comment,
    ).toBeNull();
  });

  it("handles a quote with no prior sales_checklist (legacy / empty JSONB)", async () => {
    fakeSupabase.existingChecklist = null;
    const res = await updateDistributionComment("q-1", "Первое уточнение");
    expect(res.success).toBe(true);
    expect(fakeSupabase.updatePayload?.sales_checklist).toEqual({
      distribution_comment: "Первое уточнение",
    });
  });

  it("scopes both read and write by quote id + organization_id", async () => {
    fakeSupabase.existingChecklist = {};
    await updateDistributionComment("q-42", "hint");
    expect(fakeSupabase.readEqCalls).toEqual([
      ["id", "q-42"],
      ["organization_id", "org-1"],
    ]);
    expect(fakeSupabase.updateEqCalls).toEqual([
      ["id", "q-42"],
      ["organization_id", "org-1"],
    ]);
  });
});

describe("updateDistributionComment — error paths", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["sales"] };
  });

  it("propagates read errors", async () => {
    fakeSupabase.readError = new Error("read failed");
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(false);
    expect(res.error).toBe("read failed");
    expect(fakeSupabase.updatePayload).toBeNull();
  });

  it("propagates update errors", async () => {
    fakeSupabase.existingChecklist = {};
    fakeSupabase.updateError = new Error("update failed");
    const res = await updateDistributionComment("q-1", "hint");
    expect(res.success).toBe(false);
    expect(res.error).toBe("update failed");
  });
});
