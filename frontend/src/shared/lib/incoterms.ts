/**
 * Shared Incoterms 2020 constant — single source of truth for every dropdown
 * in the app that lets users pick delivery terms. Consumers: supplier invoice
 * create modal, new-quote dialog, calculation form.
 *
 * Labels are the standard English names per the ICC Incoterms 2020 standard.
 * Consumers should localize at display time — do not add per-locale variants here.
 *
 * Codes are ordered by standard category (E-term, F-terms, C-terms, D-terms).
 */

export interface Incoterm {
  readonly code: string;
  readonly label: string;
}

export const INCOTERMS_2020: readonly Incoterm[] = [
  { code: "EXW", label: "Ex Works" },
  { code: "FCA", label: "Free Carrier" },
  { code: "CPT", label: "Carriage Paid To" },
  { code: "CIP", label: "Carriage and Insurance Paid To" },
  { code: "DAP", label: "Delivered at Place" },
  { code: "DPU", label: "Delivered at Place Unloaded" },
  { code: "DDP", label: "Delivered Duty Paid" },
  { code: "FAS", label: "Free Alongside Ship" },
  { code: "FOB", label: "Free on Board" },
  { code: "CFR", label: "Cost and Freight" },
  { code: "CIF", label: "Cost, Insurance and Freight" },
];

/**
 * Returns true when `code` matches one of the 11 Incoterms 2020 codes,
 * case-insensitive and whitespace-trimmed. Returns false for null/undefined/empty.
 */
export function isValidIncoterm(code: string | null | undefined): boolean {
  if (!code) return false;
  const upper = code.toUpperCase().trim();
  return INCOTERMS_2020.some((i) => i.code === upper);
}

/**
 * Incoterms under which the supplier covers the first logistics segment
 * (supplier's warehouse → first hub) at their own expense. Testing 2 row 44
 * — these flip the first segment's cost input to read-only zero in the
 * route constructor.
 *
 * Scope (per Andrey's clarification 2026-05-23):
 *   - D-terms (DAP/DPU/DDP): supplier delivers to a named place; always
 *     covers segment 1.
 *   - C-terms (CPT/CIP/CFR/CIF): supplier prepays carriage to destination;
 *     covers segment 1.
 * Out of scope (buyer covers segment 1):
 *   - EXW: buyer picks up at supplier.
 *   - FCA / FAS / FOB (F-terms): buyer takes over at carrier/port — segment 1
 *     is buyer's responsibility under our routing model.
 */
export const SUPPLIER_DELIVERS_FIRST_SEGMENT_INCOTERMS: ReadonlySet<string> =
  new Set(["DAP", "DPU", "DDP", "CPT", "CIP", "CFR", "CIF"]);

/**
 * Returns true when `supplier_incoterms` implies the supplier covers the
 * first logistics segment. Null/empty/EXW → false (buyer pays).
 */
export function supplierDeliversFirstSegment(
  incoterms: string | null | undefined,
): boolean {
  if (!incoterms) return false;
  return SUPPLIER_DELIVERS_FIRST_SEGMENT_INCOTERMS.has(
    incoterms.toUpperCase().trim(),
  );
}
