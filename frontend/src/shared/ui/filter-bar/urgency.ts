/**
 * Срочность buckets (Testing 2 rows 64-65).
 *
 * Bucketing is computed from a deadline timestamp + the current clock. The
 * filter is single-select — picking one bucket replaces any previous pick.
 */

export type UrgencyBucket =
  | "overdue"
  | "le_1d"
  | "le_3d"
  | "le_7d";

export const URGENCY_LABELS: Record<UrgencyBucket, string> = {
  overdue: "Просрочено",
  le_1d: "≤ 1 день",
  le_3d: "≤ 3 дня",
  le_7d: "≤ 7 дней",
};

export const URGENCY_OPTIONS: ReadonlyArray<{
  value: UrgencyBucket;
  label: string;
}> = [
  { value: "overdue", label: URGENCY_LABELS.overdue },
  { value: "le_1d", label: URGENCY_LABELS.le_1d },
  { value: "le_3d", label: URGENCY_LABELS.le_3d },
  { value: "le_7d", label: URGENCY_LABELS.le_7d },
];

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/**
 * Test whether a deadline timestamp falls into the given urgency bucket
 * relative to `now`. Returns false when the deadline is missing (cards
 * without a deadline are not "urgent" — they can't be overdue or due soon).
 *
 * Semantics:
 *  - `overdue`: deadline < now (already past).
 *  - `le_1d`:  deadline in [now, now + 1d].
 *  - `le_3d`:  deadline in [now, now + 3d].
 *  - `le_7d`:  deadline in [now, now + 7d].
 *
 * `le_3d` and `le_7d` are inclusive supersets of tighter buckets — that
 * matches the natural "anything due within 3 days" reading from the tester
 * («покажи все, что горит в ближайшие N дней»).
 */
export function isInUrgencyBucket(
  deadlineIso: string | null | undefined,
  bucket: UrgencyBucket,
  now: Date = new Date()
): boolean {
  if (!deadlineIso) return false;
  const deadline = new Date(deadlineIso);
  if (Number.isNaN(deadline.getTime())) return false;

  const deltaMs = deadline.getTime() - now.getTime();

  if (bucket === "overdue") return deltaMs < 0;
  if (deltaMs < 0) {
    // Already overdue — exclude from the «in next N days» buckets so
    // «Просрочено» stays disjoint from the upcoming-window buckets.
    return false;
  }

  const windowDays =
    bucket === "le_1d" ? 1 : bucket === "le_3d" ? 3 : bucket === "le_7d" ? 7 : 0;
  return deltaMs <= windowDays * MS_PER_DAY;
}
