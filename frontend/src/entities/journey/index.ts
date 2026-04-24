// Public API for the `journey` entity slice.
// Task 2 surfaced the type contracts. Task 14 adds the runtime surface:
// access helpers, TanStack Query hooks, Supabase direct queries, and the
// optimistic-mutation hook for state PATCH.

export type {
  // Status unions
  ImplStatus,
  QaStatus,
  GhostStatus,
  PinMode,
  VerifyResult,
  // Role + identifier
  RoleSlug,
  JourneyNodeId,
  // Manifest
  JourneyStory,
  JourneyNode,
  JourneyEdge,
  JourneyCluster,
  JourneyManifest,
  // Annotations
  JourneyNodeState,
  JourneyNodeStateHistory,
  JourneyGhostNode,
  JourneyPin,
  JourneyVerification,
  JourneyFlow,
  JourneyFlowStep,
  // API response shapes
  JourneyNodeAggregated,
  JourneyFeedbackSummary,
  JourneyNodeDetail,
  JourneyNodeHistoryEntry,
  // Supabase row aliases (stubbed until Task 1 types land)
  JourneyNodeStateRow,
  JourneyNodeStateHistoryRow,
  JourneyGhostNodeRow,
  JourneyPinRow,
  JourneyVerificationRow,
  JourneyFlowRow,
} from "./types";

// Access control
export {
  IMPL_STATUS_WRITERS,
  QA_STATUS_WRITERS,
  NOTES_WRITERS,
  GHOST_WRITERS,
  PIN_WRITERS,
  VERIFICATION_WRITERS,
  TRAINING_WRITERS,
  canEditImpl,
  canEditQa,
  canEditNotes,
  canCreateGhost,
  canCreatePin,
  canRecordVerification,
  canEditTraining,
} from "./access";

// API hooks (TanStack Query)
export {
  journeyNodePath,
  journeyFetch,
  useNodes,
  useNodeDetail,
  useNodeHistory,
  useFlows,
  JOURNEY_QUERY_KEYS,
} from "./api";

// Supabase direct queries
export {
  listGhosts,
  createGhost,
  updateGhost,
  deleteGhost,
  listPinsForNode,
  createPin,
  updatePin,
  deletePin,
  listVerificationsForPin,
  createVerification,
  listFlows,
} from "./queries";

// Mutations
export { useUpdateNodeState } from "./mutations";
