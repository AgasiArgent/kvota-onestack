import { describe, expect, it } from "vitest";
import path from "path";
import { parseRoles } from "../parse-roles";

const FIXTURE = path.resolve(__dirname, "fixtures/access-control.md");

describe("parse-roles", () => {
  it("builds a role × cluster visibility matrix from the markdown", async () => {
    const matrix = await parseRoles(FIXTURE);

    // Every active role slug present.
    expect(Object.keys(matrix).sort()).toEqual(
      [
        "admin",
        "top_manager",
        "head_of_sales",
        "head_of_procurement",
        "head_of_logistics",
        "sales",
        "quote_controller",
        "spec_controller",
        "finance",
        "procurement",
        "procurement_senior",
        "logistics",
        "customs",
      ].sort(),
    );
  });

  it("grants admin and top_manager full visibility across all clusters", async () => {
    const matrix = await parseRoles(FIXTURE);

    for (const cluster of ["customers", "quotes", "specifications", "suppliers"]) {
      expect(matrix.admin[cluster]).toBe(true);
      expect(matrix.top_manager[cluster]).toBe(true);
    }
  });

  it("denies procurement tiers access to customers but grants access to quotes", async () => {
    const matrix = await parseRoles(FIXTURE);

    // Customers are gated away from procurement/logistics/customs.
    expect(matrix.procurement.customers).toBe(false);
    expect(matrix.logistics.customers).toBe(false);
    expect(matrix.customs.customers).toBe(false);
    expect(matrix.head_of_procurement.customers).toBe(false);

    // Quotes: procurement tiers DO see quotes (assigned items / all stages).
    expect(matrix.procurement.quotes).toBe(true);
    expect(matrix.head_of_procurement.quotes).toBe(true);
    expect(matrix.procurement_senior.quotes).toBe(true);
  });

  it("grants sales and head_of_sales access to customers and quotes", async () => {
    const matrix = await parseRoles(FIXTURE);

    expect(matrix.sales.customers).toBe(true);
    expect(matrix.sales.quotes).toBe(true);
    expect(matrix.head_of_sales.customers).toBe(true);
    expect(matrix.head_of_sales.quotes).toBe(true);
  });

  it("denies non-procurement roles access to suppliers", async () => {
    const matrix = await parseRoles(FIXTURE);

    // admin + top_manager see suppliers.
    expect(matrix.admin.suppliers).toBe(true);
    expect(matrix.top_manager.suppliers).toBe(true);
    // procurement family sees suppliers.
    expect(matrix.head_of_procurement.suppliers).toBe(true);
    expect(matrix.procurement_senior.suppliers).toBe(true);
    expect(matrix.procurement.suppliers).toBe(true);
    // "All other roles" denied.
    expect(matrix.sales.suppliers).toBe(false);
    expect(matrix.head_of_sales.suppliers).toBe(false);
    expect(matrix.finance.suppliers).toBe(false);
    expect(matrix.quote_controller.suppliers).toBe(false);
    expect(matrix.logistics.suppliers).toBe(false);
    expect(matrix.customs.suppliers).toBe(false);
  });

  it("propagates 'same rules as quotes' narrative clusters (specifications)", async () => {
    const matrix = await parseRoles(FIXTURE);

    // Specifications: per the narrative, follow quotes.
    // Admin & top_manager visible. Sales visible. Procurement tiers visible (via assigned items).
    expect(matrix.admin.specifications).toBe(true);
    expect(matrix.top_manager.specifications).toBe(true);
    expect(matrix.sales.specifications).toBe(true);
    expect(matrix.procurement.specifications).toBe(true);
  });

  it("normalises cluster names to lowercase slugs", async () => {
    const matrix = await parseRoles(FIXTURE);

    // Keys on the inner record must be lowercase single-word slugs.
    const clusters = Object.keys(matrix.admin);
    for (const cluster of clusters) {
      expect(cluster).toMatch(/^[a-z][a-z0-9_]*$/);
    }
  });
});
