// Public API for the `journey` feature slice.
// Keeps internal modules (`lib/`, `ui/`) hidden — consumers import from here.

export {
  useJourneyUrlState,
  decodeFromSearchParams,
  encodeToSearchParams,
  withNode,
  withLayers,
  withViewAs,
  ALL_LAYER_IDS,
  DEFAULT_LAYERS,
} from "./lib/use-journey-url-state";

export type {
  JourneyUrlState,
  LayerId,
  UseJourneyUrlStateReturn,
} from "./lib/use-journey-url-state";

export { JourneyShell } from "./ui/journey-shell";
export { JourneySidebar } from "./ui/sidebar/journey-sidebar";

export {
  applyJourneyFilters,
  initialFilterState,
  toggleLayer,
  toggleExclusion,
  readLayersFromStorage,
  writeLayersToStorage,
  storageKeyForUser,
  useLayerPersistence,
  ALL_IMPL_FILTER_VALUES,
  ALL_QA_FILTER_VALUES,
} from "./lib/use-journey-filter";

export type {
  JourneyFilterState,
  ImplFilterValue,
  QaFilterValue,
  FilterResult,
} from "./lib/use-journey-filter";

export {
  ALLOWED_MIME,
  ATTACHMENT_BUCKET,
  MAX_ATTACHMENTS,
  MAX_FILE_BYTES,
  composeAttachmentKey,
  uploadAttachments,
  validateAttachments,
} from "./lib/attachment-upload";

export type {
  AttachmentRejection,
  AttachmentRejectionReason,
  AttachmentValidationResult,
  SupabaseRemoveFn,
  SupabaseUploadFn,
  UploadAttachmentsOptions,
  UploadAttachmentsResult,
} from "./lib/attachment-upload";

export {
  DEFAULT_SIGNED_URL_TTL_SECONDS,
  getSignedUrl,
} from "./lib/signed-url";

export type { SupabaseStorageLike } from "./lib/signed-url";
