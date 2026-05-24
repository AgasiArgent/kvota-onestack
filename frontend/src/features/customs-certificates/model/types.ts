/**
 * Domain types for the customs-certificates feature (Phase B, Wave 3 Task 6).
 *
 * Mirror of the Python-side dataclasses + DB row shapes — see also:
 *   - DB rows: `frontend/src/shared/types/database.types.ts`
 *     (`quote_certificates`, `quote_certificate_items`, migration 306)
 *   - Python history dataclass:
 *     `services/quote_certificates_history.HistoryCertMatch`
 *   - API contract: 6 endpoints under `/api/customs/certificates/*`
 *     (see `api/customs.py` Phase B Task 5 handlers + design.md §4.6/§4.8.1).
 *
 * These types are the **single TypeScript source of truth** for the feature
 * — UI sub-tasks (Wave 3 7a-7f) and wiring tasks (Wave 4) all import from
 * here via the public `index.ts` barrel. Cross-language parity is enforced
 * by the API envelope and the cost-split fixtures, NOT by structural
 * matching against a generated schema.
 */
import type { ApiResponse } from "@/shared/lib/api";

// ---------------------------------------------------------------------------
// Certificate (server response shape)
// ---------------------------------------------------------------------------

/**
 * One attached quote-position with its computed kopek-exact cost share.
 *
 * Mirrors the JSON object the API returns inside `Certificate.attached_items`
 * — server pre-computes `share_rub` and `share_percent` via
 * `services.cost_split.split_cost_batch` so the frontend never has to do it
 * itself for a `read` (the cost-split lib is still bundled for the
 * live-preview math inside `CertificateModal` / `LivePreviewPanel`).
 *
 * The order of items within `attached_items[]` is `created_at ASC` —
 * the same order used to derive the proportional shares server-side, so
 * "the last item absorbs the residual" stays deterministic across requests.
 */
export interface AttachedItem {
  /** UUID of the `quote_items` row this attachment refers to. */
  item_id: string;
  /** Kopek-exact RUB share of the certificate cost (may be 0). */
  share_rub: number;
  /** Percentage share (0..100) — informational only, not used for math. */
  share_percent: number;
}

/**
 * Full certificate row + its computed attachment payload.
 *
 * Field-by-field parity with `kvota.quote_certificates` columns +
 * `_serialize_cert()` in `api/customs.py` (which casts NUMERIC `cost_rub`
 * → `float` for JSON transport — frontend receives it as a `number`).
 *
 * `is_custom_expense=true` rows represent "Свой расход" (REQ-10) and have a
 * non-null `display_name` instead of `type`-based identification — the UI
 * branches on this flag to render `<CustomExpenseCard>` vs `<CertificateCard>`.
 */
export interface Certificate {
  /** UUID primary key. */
  id: string;
  /** UUID of the parent `quotes` row. */
  quote_id: string;
  /**
   * Certificate type — free-form string with seeded suggestions
   * (`["ДС ТР ТС", "СС", "СГР", "ОТТС", "EUR.1", ...]`) or
   * `"custom_expense"` when `is_custom_expense=true` (REQ-10).
   */
  type: string;
  /** Document number — optional. */
  number: string | null;
  /** Issuing body — optional. */
  issuer: string | null;
  /** Legal-doc reference (e.g. ТР ТС 010/2011) — optional. */
  legal_doc: string | null;
  /** ISO date `YYYY-MM-DD` of issuance — optional. */
  issued_at: string | null;
  /**
   * ISO date `YYYY-MM-DD` of expiry — optional.
   * `null` means "no expiry / perpetual" (REQ-4 AC#5: treated as actual).
   */
  valid_until: string | null;
  /**
   * Certificate cost in its original currency. CHECK constraint
   * ``cost_original >= 0`` on DB (renamed from ``cost_rub`` in migration 322).
   * Optional on the type so legacy test fixtures + pre-migration response
   * shapes (which only had ``cost_rub``) still satisfy the structural check.
   * The server always emits this since migration 322.
   */
  cost_original?: number;
  /**
   * ISO 4217 currency code for ``cost_original`` (RUB / USD / EUR / CNY / …).
   * Added in migration 322. Defaults to ``'RUB'`` for pre-migration rows.
   * Optional on the type for the same reason as ``cost_original``.
   */
  cost_currency?: string;
  /**
   * RUB-equivalent of ``cost_original`` derived server-side via the live FX
   * table. Kept on the envelope so the existing display layer (cards, totals,
   * history banner) can keep rendering in RUB without re-running FX
   * conversions in the browser. Always present (defaults to 0).
   */
  cost_rub: number;
  /** Free-form notes — optional. */
  notes: string | null;
  /** "Свой расход" label, only set when `is_custom_expense=true` (REQ-10). */
  display_name: string | null;
  /** True for "Свой расход" rows that bypass cert-specific fields. */
  is_custom_expense: boolean;
  /** ISO timestamp — server-managed. */
  created_at: string;
  /** ISO timestamp — server-managed. */
  updated_at: string;
  /** UUID of the user who created the row. May be null for backfilled rows. */
  created_by: string | null;
  /**
   * Computed attachments — kopek-exact shares derived from the upstream
   * `quote_items` RUB basis. See `AttachedItem` notes.
   */
  attached_items: AttachedItem[];
}

// ---------------------------------------------------------------------------
// History match (REQ-5)
// ---------------------------------------------------------------------------

/**
 * Loose 2-of-3 history match returned by `GET /api/customs/certificates/history`.
 *
 * **Mirrors `services.quote_certificates_history.HistoryCertMatch`**
 * field-for-field. Any drift between the Python dataclass and this interface
 * MUST be reconciled — the API endpoint serializes the dataclass directly.
 *
 * The matcher returns the most recent (`ORDER BY created_at DESC LIMIT 1`)
 * non-custom certificate from the same organization, within a 12-month
 * window, attached to a `quote_items` row that satisfies ≥2 of the
 * `(hs_code, brand, supplier_id)` predicate.
 *
 * `is_actual` is the freshness flag — `valid_until IS NULL OR > today`. It
 * drives the `HistoryBanner` variant: `'apply'` (info-blue) vs `'create-new'`
 * (amber) — REQ-4 AC#5/#6.
 */
export interface HistoryCertMatch {
  /** UUID of the matched certificate. */
  cert_id: string;
  /** Cert type, e.g. "ДС ТР ТС". */
  type: string;
  /** Cert number — optional. */
  number: string | null;
  /** Issuer — optional. */
  issuer: string | null;
  /** Legal-doc reference — optional. */
  legal_doc: string | null;
  /** ISO date — optional. */
  issued_at: string | null;
  /** ISO date — optional. */
  valid_until: string | null;
  /** Cost in RUB. */
  cost_rub: number;
  /** ISO timestamp of the matched cert's creation. */
  created_at: string;
  /** UUID of the source quote (NOT the current quote). */
  source_quote_id: string;
  /** UUID of the source `quote_items` row that satisfied the 2-of-3 match. */
  source_item_id: string;
  /**
   * `true` when `valid_until IS NULL OR valid_until > today`.
   * Drives `HistoryBanner` variant — `false` triggers the amber
   * "create-new" copy (REQ-4 AC#6).
   */
  is_actual: boolean;
}

// ---------------------------------------------------------------------------
// Quote-item shape used by multi-select / live-preview panels
// ---------------------------------------------------------------------------

/**
 * Minimal quote-item shape consumed by the multi-select + live-preview
 * components inside the certificate modals (REQ-7 / REQ-10) and the bind
 * popover (REQ-8) and coverage list (REQ-9).
 *
 * The wider `quote_items` row has dozens of columns; the cert UI only
 * needs the human-readable label fields plus the **pre-derived RUB basis**
 * — i.e. `purchase_price_original × quantity × currency_rate_to_rub`,
 * computed once by the parent component (e.g. `customs-step.tsx`) and
 * passed down as the `rub_basis` field.
 *
 * The derivation formula lives in the cost-split parity contract
 * (REQ-3 AC#4) — kept in upstream callers so the cert feature can stay
 * decoupled from the upstream price-conversion concerns.
 */
export interface QuoteItemForSelect {
  /** UUID of the `quote_items` row. */
  id: string;
  /** 1-based ordinal within the quote (rendered as "№N"). */
  position: number;
  /** Display name — usually `product_name`. */
  name: string;
  /** SKU / vendor code — optional. */
  product_code: string | null;
  /**
   * RUB cost basis used to weight the proportional cost-split.
   * Computed upstream — see component contract above.
   */
  rub_basis: number;
}

// ---------------------------------------------------------------------------
// System view (Wave 3 forward declaration for Task 8 / Task 9)
// ---------------------------------------------------------------------------

/**
 * Synthetic, client-side "view" used by the customs Handsontable to switch
 * column-visibility presets (REQ-11). Defined here to give Wave 3 (UI
 * sub-tasks) a stable type contract that Wave 4 (Task 8) implements as
 * `frontend/src/features/quotes/ui/customs-step/customs-views.ts`.
 *
 * The `id` template-literal type (`` `system:${string}` ``) prevents
 * collisions with UUID rows in `kvota.user_table_views` — synthetic IDs
 * are always prefixed `system:` per design.md §4.11 + LD-16.
 */
export interface SystemView {
  /** Synthetic ID, e.g. `'system:all'`, `'system:tariffs-nds'`. */
  readonly id: `system:${string}`;
  /** Russian label rendered in the dropdown. */
  readonly label: string;
  /** Column ids visible under this view — verified vs `customs-columns.ts`. */
  readonly visibleColumnIds: readonly string[];
  /** Always `true` for system views — the dropdown groups by this flag. */
  readonly is_system: true;
}

// ---------------------------------------------------------------------------
// API request input
// ---------------------------------------------------------------------------

/**
 * Body of `POST /api/customs/certificates` — see
 * `create_certificate_handler` in `api/customs.py`.
 *
 * Server validates: `quote_id` and `type` non-empty, `cost_rub >= 0`,
 * `item_ids` is a list (may be empty), each `item_ids[]` belongs to the
 * same quote (cross-quote attempts → 422 `NOT_IN_QUOTE`).
 */
export interface CreateCertificateInput {
  /** UUID of the parent quote. */
  quote_id: string;
  /** Cert type or `"custom_expense"`. */
  type: string;
  /** Optional fields — omit or pass `undefined` to keep DB defaults. */
  number?: string;
  issuer?: string;
  legal_doc?: string;
  /** ISO date `YYYY-MM-DD`. */
  issued_at?: string;
  /** ISO date `YYYY-MM-DD`. */
  valid_until?: string;
  /**
   * Cost in the original currency; must be `>= 0`. New canonical field
   * since migration 322. The server still accepts the legacy ``cost_rub``
   * key (implicit RUB) — both are optional on the type so existing test
   * fixtures keep type-checking. The modal UI always sends the new pair.
   */
  cost_original?: number;
  /**
   * ISO 4217 currency code (RUB / USD / EUR / CNY / …). Server defaults to
   * 'RUB' when omitted. Optional on the type so legacy callers stay valid.
   */
  cost_currency?: string;
  /**
   * Legacy field — accepted by the server as a synonym for
   * ``{cost_original=value, cost_currency='RUB'}``. Kept on the type so
   * existing call sites and test fixtures don't break; new code should
   * always use the ``cost_original`` + ``cost_currency`` pair.
   */
  cost_rub?: number;
  notes?: string;
  /** Required when `is_custom_expense=true` (REQ-10). */
  display_name?: string;
  /** Defaults to `false`; `true` toggles the "Свой расход" branch (REQ-10). */
  is_custom_expense?: boolean;
  /**
   * Quote-item UUIDs to attach in the same atomic call. May be empty.
   * Server validates each is in `quote_id` (REQ-2 AC#11).
   */
  item_ids: string[];
}

// ---------------------------------------------------------------------------
// Response envelopes
// ---------------------------------------------------------------------------

/**
 * Server envelope for `GET /api/customs/certificates?quote_id=...`.
 * The server wraps the list in a `{certificates}` object so we can later
 * add pagination metadata without breaking clients.
 */
export interface ListCertificatesData {
  certificates: Certificate[];
}

/**
 * Server envelope for `GET /api/customs/certificates/history?...`.
 * `match` is `null` when no candidate satisfies the loose 2-of-3 predicate
 * (or the DB threw — history is best-effort, see Python-side fallback).
 */
export interface CertificateHistoryData {
  match: HistoryCertMatch | null;
}

/** Server envelope for `DELETE /api/customs/certificates/{cert_id}`. */
export interface DeleteCertificateData {
  deleted_id: string;
}

// Re-export the shared `ApiResponse` so feature consumers don't have to
// import from `@/shared/lib/api` separately when handling API results.
export type { ApiResponse };
