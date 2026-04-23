// Public surface of the journey-canvas subfeature.
// Tasks 17/18 (sidebar, drawer) intentionally do not import from here —
// the shell is the only integration point.

export { JourneyCanvas } from "./journey-canvas";
export { buildReactFlowGraph } from "./build-graph";
export { computeLayout } from "./auto-layout";
export type {
  JourneyNodeCardData,
  ClusterSubflowData,
  BuildGraphResult,
} from "./build-graph";
