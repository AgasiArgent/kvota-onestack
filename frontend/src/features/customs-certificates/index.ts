/**
 * Public API for the customs-certificates feature (Phase B).
 *
 * Wave 3 Task 6 — initial scaffold. UI components (Wave 3 Tasks 7a-7f)
 * will append their own re-exports here as they land. Internal helpers
 * (cards, sub-components) stay private to the feature folder per design.md
 * §4.8.5 — only the listed surface is reachable from outside.
 */

// API wrappers — REQ-2 / REQ-5
export {
  attachCertificateItem,
  createCertificate,
  deleteCertificate,
  detachCertificateItem,
  listCertificates,
} from "./api/certificates";
export { fetchCertificateHistory } from "./api/history";
export type { FetchCertificateHistoryArgs } from "./api/history";

// Domain types — single source of truth for the feature
export type {
  ApiResponse,
  AttachedItem,
  Certificate,
  CertificateHistoryData,
  CreateCertificateInput,
  DeleteCertificateData,
  HistoryCertMatch,
  ListCertificatesData,
  QuoteItemForSelect,
  SystemView,
} from "./model/types";

// Lib helpers — pure functions
export { formatRub } from "./lib/format-rub";
export {
  roundHalfUp2,
  splitCost,
  splitCostBatch,
} from "./lib/cost-split";
