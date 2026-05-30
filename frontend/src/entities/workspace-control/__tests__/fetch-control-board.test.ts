import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Tests for fetchControlBoard — the /workspace/control board fetcher
 * (control-spec-workspace task 4.2 / 4.6).
 *
 * Covered:
 *  - domain → workflow_status mapping (calc = pending_quote_control +
 *    pending_approval; spec = pending_spec_control + pending_signature).
 *  - org scoping (organization_id filter applied).
 *  - per-domain controller column (calc reads quote_controller_id; spec reads
 *    spec_controller_id) resolved to the ФИО from user_profiles.full_name.
 *  - card shape reads total_quote_currency (not total_amount).
 *
 * The DB layer is mocked via a fluent fake-supabase admin client that records
 * the filter chain applied to the `quotes` SELECT.
 */

// `queries.ts` is server-only; the guard package isn't installed in the test
// runtime, so stub it to an empty module.
vi.mock("server-only", () => ({}));

vi.mock("@/shared/lib/supabase/server", () => ({
  createAdminClient: () => fakeAdmin,
}));

interface QueryRecord {
  filters: Array<{ op: string; col: string; val: unknown }>;
}

interface FakeAdmin {
  quoteRows: unknown[];
  profiles: Array<{ user_id: string; full_name: string | null }>;
  quoteQueries: QueryRecord[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  from(table: string): any;
}

let fakeAdmin: FakeAdmin;

function makeFakeAdmin(): FakeAdmin {
  const state: FakeAdmin = {
    quoteRows: [],
    profiles: [],
    quoteQueries: [],
    from(table: string) {
      if (table === "quotes") {
        const record: QueryRecord = { filters: [] };
        state.quoteQueries.push(record);
        const result = { data: state.quoteRows, error: null };
        const builder: Record<string, unknown> = {
          then: (onFulfilled: (v: typeof result) => unknown) =>
            Promise.resolve(result).then(onFulfilled),
        };
        const chain =
          (op: string) =>
          (col: string, val?: unknown) => {
            record.filters.push({ op, col, val });
            return builder;
          };
        builder.select = () => builder;
        builder.eq = chain("eq");
        builder.is = chain("is");
        builder.in = chain("in");
        builder.order = () => builder;
        return builder;
      }
      if (table === "user_profiles") {
        return {
          select: () => ({
            in: async () => ({ data: state.profiles, error: null }),
          }),
        };
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

function makeQuoteRow(overrides: Record<string, unknown> = {}) {
  return {
    id: "q-1",
    idn_quote: "Q-202605-0001",
    workflow_status: "pending_spec_control",
    total_quote_currency: 12345,
    currency: "RUB",
    quote_controller_id: "user-calc",
    spec_controller_id: "user-spec",
    customer: { id: "c-1", name: "ООО Ромашка" },
    ...overrides,
  };
}

const USER = { id: "u-x", roles: ["spec_controller"], orgId: "org-1" };

describe("fetchControlBoard — domain → status mapping", () => {
  beforeEach(() => {
    fakeAdmin = makeFakeAdmin();
  });

  it("calc board filters on pending_quote_control + pending_approval", async () => {
    const { fetchControlBoard } = await import("../queries");
    await fetchControlBoard("calc", USER);

    const q = fakeAdmin.quoteQueries[0];
    const inFilter = q.filters.find(
      (f) => f.op === "in" && f.col === "workflow_status",
    );
    expect(inFilter?.val).toEqual([
      "pending_quote_control",
      "pending_approval",
    ]);
  });

  it("spec board filters on pending_spec_control + pending_signature", async () => {
    const { fetchControlBoard } = await import("../queries");
    await fetchControlBoard("spec", USER);

    const q = fakeAdmin.quoteQueries[0];
    const inFilter = q.filters.find(
      (f) => f.op === "in" && f.col === "workflow_status",
    );
    expect(inFilter?.val).toEqual([
      "pending_spec_control",
      "pending_signature",
    ]);
  });

  it("scopes the query to the caller's organization", async () => {
    const { fetchControlBoard } = await import("../queries");
    await fetchControlBoard("spec", USER);

    const q = fakeAdmin.quoteQueries[0];
    const orgFilter = q.filters.find(
      (f) => f.op === "eq" && f.col === "organization_id",
    );
    expect(orgFilter?.val).toBe("org-1");
  });
});

describe("fetchControlBoard — card shape & controller resolution", () => {
  beforeEach(() => {
    fakeAdmin = makeFakeAdmin();
  });

  it("shapes a card from total_quote_currency + customer name", async () => {
    fakeAdmin.quoteRows = [makeQuoteRow()];
    const { fetchControlBoard } = await import("../queries");
    const cards = await fetchControlBoard("spec", USER);

    expect(cards).toHaveLength(1);
    expect(cards[0]).toMatchObject({
      quoteId: "q-1",
      idnQuote: "Q-202605-0001",
      customerName: "ООО Ромашка",
      total: 12345,
      currency: "RUB",
      workflowStatus: "pending_spec_control",
    });
  });

  it("resolves the spec controller ФИО from spec_controller_id on the spec board", async () => {
    fakeAdmin.quoteRows = [makeQuoteRow()];
    fakeAdmin.profiles = [
      { user_id: "user-spec", full_name: "Спец Контролёр" },
      { user_id: "user-calc", full_name: "Калк Контролёр" },
    ];
    const { fetchControlBoard } = await import("../queries");
    const cards = await fetchControlBoard("spec", USER);

    expect(cards[0].controllerName).toBe("Спец Контролёр");
  });

  it("resolves the quote controller ФИО from quote_controller_id on the calc board", async () => {
    fakeAdmin.quoteRows = [
      makeQuoteRow({ workflow_status: "pending_quote_control" }),
    ];
    fakeAdmin.profiles = [
      { user_id: "user-spec", full_name: "Спец Контролёр" },
      { user_id: "user-calc", full_name: "Калк Контролёр" },
    ];
    const { fetchControlBoard } = await import("../queries");
    const cards = await fetchControlBoard("calc", {
      ...USER,
      roles: ["quote_controller"],
    });

    expect(cards[0].controllerName).toBe("Калк Контролёр");
  });

  it("returns null controllerName when the gate is unclaimed", async () => {
    fakeAdmin.quoteRows = [makeQuoteRow({ spec_controller_id: null })];
    const { fetchControlBoard } = await import("../queries");
    const cards = await fetchControlBoard("spec", USER);

    expect(cards[0].controllerName).toBeNull();
  });
});
