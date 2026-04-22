// Public API for the `journey` entity slice.
// Task 2 surfaces the type contracts only. API clients, queries, and mutations
// arrive in Task 14 (`entities/journey/api.ts`, `queries.ts`, `mutations.ts`).

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
  // Supabase row aliases (stubbed until Task 1 types land)
  JourneyNodeStateRow,
  JourneyNodeStateHistoryRow,
  JourneyGhostNodeRow,
  JourneyPinRow,
  JourneyVerificationRow,
  JourneyFlowRow,
} from "./types";
