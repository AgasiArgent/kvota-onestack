// Client-safe barrel only — server-only data fetchers (`fetchLocations*` from
// `./queries`) must be imported directly from `@/entities/location/queries`
// in server code. Re-exporting them here would drag `import "server-only"`
// into any client component that touches this barrel for types or labels.
export {
  LocationChip,
  type LocationType,
  type LocationChipLocation,
} from "./ui/location-chip";
export {
  LOCATION_TYPE_LABEL,
  formatLocationLabel,
  type LocationOption,
} from "./lib/format";
