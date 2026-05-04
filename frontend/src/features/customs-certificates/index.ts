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

// UI sub-components — REQ-7 / REQ-10 (Wave 3 Task 7b)
//
// Per design.md §4.8.5 these stay internal-only — outside callers should
// reach for `<CertificateModal>` / `<ExpenseModal>` (Task 7c) instead.
// They are exported here so sibling UI files in this feature folder
// (`certificate-modal.tsx`, `expense-modal.tsx`, `certificate-bind-popover.tsx`)
// can import from the public surface without crossing the FSD boundary
// via deep relative paths.
export {
  PositionsMultiSelect,
  filterItems,
  toggleId,
  allFilteredSelected,
  nextSelectionAfterToggleAll,
} from "./ui/positions-multi-select";
export type { PositionsMultiSelectProps } from "./ui/positions-multi-select";
export {
  LivePreviewPanel,
  computePreviewRows,
  formatPercent,
} from "./ui/live-preview-panel";
export type {
  LivePreviewPanelProps,
  PreviewRow,
} from "./ui/live-preview-panel";

// UI components — Wave 3 Task 7a (REQ-6 AC#4 cert tile + REQ-6 AC#5 expense
// tile + REQ-4 AC#3 expired red border).
//
// Cards live behind the section (Task 7f) but the section composes them
// from this barrel — exposing them via the public surface keeps the import
// graph flat (sibling UI files don't reach into `./ui/*` directly).
export { CertificateCard } from "./ui/certificate-card";
export type { CertificateCardProps } from "./ui/certificate-card";
export { CustomExpenseCard } from "./ui/custom-expense-card";
export type { CustomExpenseCardProps } from "./ui/custom-expense-card";
