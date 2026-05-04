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

// UI components — Wave 3 Task 7f (REQ-5 HistoryBanner + REQ-6 section orchestrator)
//
// `HistoryBanner` is the per-item dialog cue that surfaces the loose 2-of-3
// match returned by `GET /api/customs/certificates/history`.
// `CertificatesSection` is the unified «Расходы по таможне» section that
// replaces the Phase A `<QuoteCustomsExpenses />` + `<ItemCustomsExpenses />`
// split — see design.md §4.8.4 + §4.9 for wiring details.
export { HistoryBanner } from "./ui/history-banner";
export type { HistoryBannerProps } from "./ui/history-banner";
export { CertificatesSection } from "./ui/certificates-section";
export type { CertificatesSectionProps } from "./ui/certificates-section";

// UI components — Wave 3 Task 7e (REQ-9 — per-item dialog read-only coverage
// list + read-only details modal). The list renders inside
// `customs-item-dialog.tsx` (Wave 4 Task 10) under the «Сертификация»
// section; the modal opens on cert-card click («Открыть сертификат» /
// «Подробнее»).
export { CertificateCoverageList } from "./ui/certificate-coverage-list";
export type {
  AttachedCertView,
  CertificateCoverageListProps,
} from "./ui/certificate-coverage-list";
export {
  CertificateDetailsBody,
  CertificateDetailsModal,
} from "./ui/certificate-details-modal";
export type {
  CertificateDetailsBodyProps,
  CertificateDetailsModalProps,
} from "./ui/certificate-details-modal";

// UI — modals (Wave 3 Task 7c, REQ-7 + REQ-10)
export { CertificateModal } from "./ui/certificate-modal";
export type { CertificateModalProps } from "./ui/certificate-modal";
export { ExpenseModal } from "./ui/expense-modal";
export type { ExpenseModalProps } from "./ui/expense-modal";

// UI — bind-to-existing popover (Wave 3 Task 7d, REQ-8). Mounted from
// `customs-item-dialog.tsx` (Wave 4 Task 10) on the empty-amber-card's
// «Привязать к существующему» button. Pure helpers re-exported so
// downstream code (and tests) can compute the after-attach preview
// without duplicating the formula.
export { CertificateBindPopover } from "./ui/certificate-bind-popover";
export type {
  AfterAttachPreviewRow,
  CertificateBindPopoverProps,
} from "./ui/certificate-bind-popover";
