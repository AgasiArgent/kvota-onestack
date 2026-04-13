/**
 * Procurement kanban substatuses — mirrors Python workflow_service.py constants.
 *
 * Transitions are an explicit adjacency list so forward vs backward moves can be
 * distinguished. Backward moves require a reason and are recorded in status_history.
 */

export const PROCUREMENT_SUBSTATUSES = [
  "distributing",
  "searching_supplier",
  "waiting_prices",
  "prices_ready",
] as const;

export type ProcurementSubstatus = (typeof PROCUREMENT_SUBSTATUSES)[number];

export const SUBSTATUS_LABELS_RU: Record<ProcurementSubstatus, string> = {
  distributing: "Распределение",
  searching_supplier: "Поиск поставщика",
  waiting_prices: "Ожидание цен",
  prices_ready: "Цены готовы",
};

/** Forward transitions — no reason required. */
export const FORWARD_TRANSITIONS: ReadonlyArray<
  readonly [ProcurementSubstatus, ProcurementSubstatus]
> = [
  ["distributing", "searching_supplier"],
  ["searching_supplier", "waiting_prices"],
  ["waiting_prices", "prices_ready"],
] as const;

/** Backward transitions — reason required. */
export const BACKWARD_TRANSITIONS: ReadonlyArray<
  readonly [ProcurementSubstatus, ProcurementSubstatus]
> = [
  ["searching_supplier", "distributing"],
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
