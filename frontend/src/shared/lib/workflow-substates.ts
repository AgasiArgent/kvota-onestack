/**
 * Procurement kanban substatuses — mirrors Python workflow_service.py constants.
 *
 * Transitions are an explicit adjacency list so forward vs backward moves can be
 * distinguished. Backward moves require a reason and are recorded in status_history.
 *
 * `paused` is a parking lot — any active column can move INTO paused and any
 * paused card can move BACK OUT to any active column. Pause is a substate,
 * not a step in the linear flow, so it's neither forward nor backward.
 */

export const PROCUREMENT_SUBSTATUSES = [
  "distributing",
  "request",
  "searching_supplier",
  "waiting_prices",
  "prices_ready",
  "paused",
] as const;

export type ProcurementSubstatus = (typeof PROCUREMENT_SUBSTATUSES)[number];

export const SUBSTATUS_LABELS_RU: Record<ProcurementSubstatus, string> = {
  distributing: "Распределение",
  request: "Заявка",
  searching_supplier: "Поиск поставщика",
  waiting_prices: "Ожидание цен",
  prices_ready: "Цены готовы",
  paused: "На паузе",
};

/** Active (non-paused) columns — used to enumerate pause↔resume transitions. */
const ACTIVE_SUBSTATUSES = [
  "distributing",
  "request",
  "searching_supplier",
  "waiting_prices",
  "prices_ready",
] as const satisfies readonly ProcurementSubstatus[];

/** Forward transitions — no reason required. */
export const FORWARD_TRANSITIONS: ReadonlyArray<
  readonly [ProcurementSubstatus, ProcurementSubstatus]
> = [
  // «Заявка» (Testing 2 row 95a) is the new first stop after distribution.
  // The МОЗ pulls request → searching_supplier manually.
  ["distributing", "request"],
  ["request", "searching_supplier"],
  ["searching_supplier", "waiting_prices"],
  ["waiting_prices", "prices_ready"],
  // Pause from any active column — treated as a forward (no reason) move.
  ...ACTIVE_SUBSTATUSES.map(
    (s) => [s, "paused"] as [ProcurementSubstatus, ProcurementSubstatus]
  ),
  // Resume from paused back to any active column — also no reason required:
  // resuming work doesn't carry the same "why are you reverting" friction as
  // a true backward step. If we later want a resume reason, add it here.
  ...ACTIVE_SUBSTATUSES.map(
    (s) => ["paused", s] as [ProcurementSubstatus, ProcurementSubstatus]
  ),
] as const;

/** Backward transitions — reason required. */
export const BACKWARD_TRANSITIONS: ReadonlyArray<
  readonly [ProcurementSubstatus, ProcurementSubstatus]
> = [
  ["request", "distributing"],
  ["searching_supplier", "request"],
  ["waiting_prices", "searching_supplier"],
  ["prices_ready", "waiting_prices"],
] as const;

export function isBackwardTransition(
  from: ProcurementSubstatus,
  to: ProcurementSubstatus
): boolean {
  return BACKWARD_TRANSITIONS.some(([f, t]) => f === from && t === to);
}

export function isValidTransition(
  from: ProcurementSubstatus,
  to: ProcurementSubstatus
): boolean {
  if (from === to) return false;
  return (
    FORWARD_TRANSITIONS.some(([f, t]) => f === from && t === to) ||
    BACKWARD_TRANSITIONS.some(([f, t]) => f === from && t === to)
  );
}

export function isProcurementSubstatus(
  value: string
): value is ProcurementSubstatus {
  return (PROCUREMENT_SUBSTATUSES as readonly string[]).includes(value);
}
