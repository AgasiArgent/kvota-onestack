/**
 * Public API for the `kp-proposal` entity slice.
 *
 * Anything other slices need to read about a КП proposal goes through this
 * barrel — never reach into `model/` or `lib/` directly.
 */

export type {
  KpItem,
  KpPackagingItem,
  KpServices,
  KpProposal,
  CurrencyCode,
} from "./model/types";
export {
  CURRENCIES,
  currencyEntry,
  currencySymbol,
  headlineSuffix,
} from "./lib/currency";
export type { CurrencyEntry } from "./lib/currency";
export {
  kpProposalSchema,
  kpItemSchema,
  kpPackagingItemSchema,
  kpServicesSchema,
} from "./model/schema";
export type { KpProposalInput } from "./model/schema";
export { DEFAULT_PROPOSAL } from "./model/default-data";
export { EMPTY_PROPOSAL } from "./model/empty-data";
export { BRANDING } from "./model/branding";
export type { KpBranding } from "./model/branding";
export { fmtRu } from "./lib/fmt-ru";
export { calcRowTotal, calcGrandTotal } from "./lib/calc-total";
export {
  useKpState,
  KP_STORAGE_KEY,
  KP_ZOOM_STORAGE_KEY,
} from "./lib/use-kp-state";
export type { UseKpStateReturn } from "./lib/use-kp-state";
