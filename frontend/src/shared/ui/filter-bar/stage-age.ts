/**
 * "На этапе > N дней" buckets for the procurement kanban (Testing 2 row 66).
 *
 * Buckets are mutually exclusive lower bounds, matching the tester's
 * reading: "more than 7 / 14 / 30 days in the current sub-status". The
 * value compared is `days_in_state` returned by the kanban API.
 */

export type StageAgeBucket = "gt_7" | "gt_14" | "gt_30";

export const STAGE_AGE_LABELS: Record<StageAgeBucket, string> = {
  gt_7: "> 7 дней",
  gt_14: "> 14 дней",
  gt_30: "> 30 дней",
};

export const STAGE_AGE_OPTIONS: ReadonlyArray<{
  value: StageAgeBucket;
  label: string;
}> = [
  { value: "gt_7", label: STAGE_AGE_LABELS.gt_7 },
  { value: "gt_14", label: STAGE_AGE_LABELS.gt_14 },
  { value: "gt_30", label: STAGE_AGE_LABELS.gt_30 },
];

const THRESHOLDS: Record<StageAgeBucket, number> = {
  gt_7: 7,
  gt_14: 14,
  gt_30: 30,
};

export function isInStageAgeBucket(
  daysInState: number,
  bucket: StageAgeBucket
): boolean {
  if (!Number.isFinite(daysInState)) return false;
  return daysInState > THRESHOLDS[bucket];
}
