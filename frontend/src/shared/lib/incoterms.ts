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
