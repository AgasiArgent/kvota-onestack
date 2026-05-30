/**
 * Canonical column list for fetching a full specification row.
 *
 * Shared by the server loader (`queries.ts::fetchSpecificationByQuote`) and the
 * client-side refetch (`specification-step.tsx`) so the two SELECTs never drift.
 * Keep in sync with the `SpecificationRow` interface in `queries.ts`.
 *
 * Lives in its own zero-import module (not `queries.ts`, which pulls the
 * server-only Supabase client) so the client component can import it without
 * bundling server code.
 *
 * NOTE (control-spec-workspace): `seller_company_id`, `signing_fx_mode` and
 * `signing_fx_rate` are added by migration 334 — a live query referencing them
 * fails until that migration is applied to the target database.
 */
export const SPECIFICATION_SELECT = [
  "id",
  "quote_id",
  "quote_version_id",
  "contract_id",
  "specification_number",
  "sign_date",
  "status",
  "readiness_period",
  "signed_scan_url",
  "created_at",
  "updated_at",
  // Реквизиты (requisites block)
  "our_legal_entity",
  "client_legal_entity",
  "seller_company_id",
  "cargo_pickup_country",
  "goods_shipment_country",
  "supplier_payment_country",
  // Условия спецификации (conditions block)
  "validity_period",
  "logistics_period",
  "cargo_type",
  "delivery_city_russia",
  // Контроль (control stamp — at-signing FX)
  "signing_fx_mode",
  "signing_fx_rate",
  // Audit / signed scan
  "created_by",
  "signed_scan_document_id",
].join(", ");
