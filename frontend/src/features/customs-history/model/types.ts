/**
 * Types for the customs-history feature (Phase A Req 10, Task 11).
 *
 * Mirrors the JSON envelope returned by `GET /api/customs/items/history` —
 * see `services.customs_user_choices.HistoryMatch` and the
 * `_history_lookup_handler` response in `api/customs.py`.
 *
 * `chosen_variants` is `Record<payment_type, serialized Rate | null>` where
 * each Rate snapshot mirrors `services.alta_client.Rate` field-for-field
 * (see `_serialize_rate` in `services/customs_user_choices.py`). Kept loose
 * (`Record<string, unknown>`) on the frontend — UI consumers cherry-pick
 * known payment_type keys (IMP, NDS, IMPDEMP, ...).
 */

export interface HistoryMatch {
  /** UUID of the customs specialist who saved the choice. */
  user_id: string;
  /** Email joined from auth.users. May be null when the user was deleted. */
  user_email: string | null;
  /** ISO 8601 timestamp of when the choice was logged. */
  created_at: string;
  /** Map of payment_type → serialized Rate dataclass (or null). */
  chosen_variants: Record<string, unknown>;
  /** True when manual mode was active — `manual_rate_payload` carries the slots. */
  manual_override: boolean;
  /** When `manual_override=true`, the JSONB Rate snapshot saved verbatim. */
  manual_rate_payload: Record<string, unknown> | null;
  /**
   * False when Alta has changed available variants since this choice was
   * made — UI surfaces a warning style + alternate text.
   */
  is_actual: boolean;
}
