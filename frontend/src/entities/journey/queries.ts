/**
 * Supabase direct queries for the Customer Journey Map.
 *
 * Some journey mutations are simple CRUD against tables whose RLS policies
 * already enforce the role rules (see `.kiro/specs/customer-journey-map/
 * design.md` §6 and Req 12). Per the project's API-First rule, CRUD without
 * multi-table side effects goes straight to Supabase — business logic
 * (impl/qa state writes) goes through the Python API.
 *
 * Tables touched here:
 *   - journey_ghost_nodes    (admin CUD, Req 7.1 + 12.5)
 *   - journey_pins           (admin / quote_controller / spec_controller CUD, Req 8.1 + 12.6)
 *   - journey_verifications  (same as pins, INSERT only — Req 9.1 + 12.7)
 *   - journey_flows          (read-only for now; admin-managed out of band)
 *
 * Caller contract: every function returns `{ data, error }` — callers
 * decide whether to throw or surface errors in the UI. RLS denies are
 * surfaced as `error` rows, not thrown.
 *
 * The Supabase client is configured with `db: { schema: "kvota" }` in
 * `shared/lib/supabase/client.ts`, so table names are bare (`journey_*`).
 * Calling sites must obtain a fresh browser client per invocation — the
 * factory handles auth-cookie state.
 */

import { createClient } from "@/shared/lib/supabase/client";
import type {
  JourneyFlow,
  JourneyGhostNode,
  JourneyNodeId,
  JourneyPin,
  JourneyVerification,
} from "./types";

// ---------------------------------------------------------------------------
// Ghost nodes (admin CUD)
// ---------------------------------------------------------------------------

/** Fetch every ghost node. RLS allows SELECT for all authenticated users. */
export async function listGhosts() {
  const supabase = createClient();
  return supabase.from("journey_ghost_nodes").select("*");
}

/** Create a ghost node. RLS requires `admin`. */
export async function createGhost(
  ghost: Omit<JourneyGhostNode, "id" | "created_at">
) {
  const supabase = createClient();
  return supabase.from("journey_ghost_nodes").insert(ghost).select().single();
}

/** Patch a ghost node. RLS requires `admin`. */
export async function updateGhost(id: string, patch: Partial<JourneyGhostNode>) {
  const supabase = createClient();
  return supabase.from("journey_ghost_nodes").update(patch).eq("id", id).select().single();
}

/** Delete a ghost node. RLS requires `admin`. */
export async function deleteGhost(id: string) {
  const supabase = createClient();
  return supabase.from("journey_ghost_nodes").delete().eq("id", id);
}

// ---------------------------------------------------------------------------
// Pins (admin / quote_controller / spec_controller CUD)
// ---------------------------------------------------------------------------

/** Fetch all pins for a given node. */
export async function listPinsForNode(nodeId: JourneyNodeId) {
  const supabase = createClient();
  return supabase.from("journey_pins").select("*").eq("node_id", nodeId);
}

/** Create a pin. RLS requires one of `admin`, `quote_controller`, `spec_controller`. */
export async function createPin(
  pin: Omit<
    JourneyPin,
    | "id"
    | "created_at"
    | "last_rel_x"
    | "last_rel_y"
    | "last_rel_width"
    | "last_rel_height"
    | "last_position_update"
    | "selector_broken"
  >
) {
  const supabase = createClient();
  return supabase.from("journey_pins").insert(pin).select().single();
}

/** Patch a pin (e.g. update `expected_behavior`). */
export async function updatePin(id: string, patch: Partial<JourneyPin>) {
  const supabase = createClient();
  return supabase.from("journey_pins").update(patch).eq("id", id).select().single();
}

/** Delete a pin. */
export async function deletePin(id: string) {
  const supabase = createClient();
  return supabase.from("journey_pins").delete().eq("id", id);
}

// ---------------------------------------------------------------------------
// Verifications (append-only)
// ---------------------------------------------------------------------------

/** Fetch every verification recorded against a pin, newest first. */
export async function listVerificationsForPin(pinId: string) {
  const supabase = createClient();
  return supabase
    .from("journey_verifications")
    .select("*")
    .eq("pin_id", pinId)
    .order("tested_at", { ascending: false });
}

/**
 * Append a verification event. RLS allows INSERT for QA writers;
 * UPDATE and DELETE are denied for every role (Req 9.2).
 *
 * Note: `attachment_urls` is typed `readonly string[]` in the domain model
 * but the generated Supabase types expect the mutable `Json` shape. We
 * spread into a fresh object whose `attachment_urls` is a plain array so
 * the insert signature is satisfied without weakening the public type.
 */
export async function createVerification(
  verification: Omit<JourneyVerification, "id" | "tested_at">
) {
  const supabase = createClient();
  const row = {
    ...verification,
    attachment_urls: verification.attachment_urls
      ? [...verification.attachment_urls]
      : null,
  };
  return supabase.from("journey_verifications").insert(row).select().single();
}

// ---------------------------------------------------------------------------
// Flows (read-only from the UI for now)
// ---------------------------------------------------------------------------

/** Fetch every non-archived flow, sorted for sidebar rendering. */
export async function listFlows() {
  const supabase = createClient();
  return supabase
    .from("journey_flows")
    .select("*")
    .eq("is_archived", false)
    .order("display_order", { ascending: true })
    .returns<JourneyFlow[]>();
}
