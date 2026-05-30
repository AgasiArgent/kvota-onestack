/**
 * Public API of the workspace-control entity.
 *
 * Only client-safe types are re-exported here. `fetchControlBoard` lives in
 * `./queries` (a `server-only` module) and is imported directly by the server
 * page — re-exporting a server-only value through this barrel would let a
 * client component pull it in transitively and break `next build`.
 */
export type {
  ControlKanbanCard,
  ControlBoardDomain,
} from "./model/types";
export {
  CALC_BOARD_STATUSES,
  SPEC_BOARD_STATUSES,
  boardStatuses,
} from "./model/types";
