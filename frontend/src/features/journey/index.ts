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
