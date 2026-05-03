/**
 * Types for the customs-classify feature (Phase 2).
 *
 * Mirrors the JSON envelope of `POST /api/customs/classify` and
 * `POST /api/customs/classify/select`. See `api/customs.py:_serialize_*`
 * and `services/classifier.py` for the source-of-truth shapes.
 */

export interface Candidate {
  code: string;              // 10-digit ТН ВЭД
  probability: number;       // 0.0..1.0 (Alta ML confidence)
  code_weight: number;       // Internal Alta ranking signal
  description: string | null; // Best-effort label from local cache
}

export interface ClassifyInput {
  name: string;
  brand?: string | null;
  description?: string | null;
  quote_item_id?: string | null;
}

export interface ClassifyResult {
  input_idx: number;          // 1-based — matches request order
  name: string;               // echo for UI
  quote_item_id: string | null;
  candidates: Candidate[];
  error: string | null;       // populated when Alta returned no candidates
}

export interface ClassifyData {
  results: ClassifyResult[];
  packet_left: number | null;
  packet_used: number | null;
  request_id: string;
}

export interface ClassifySelectRequest {
  quote_item_id: string;
  chosen_code: string;
  candidates_shown?: Candidate[];
  input_text?: string;
}

export interface ClassifySelectData {
  quote_item_id: string;
  hs_code: string;
}

export interface ApiError {
  code: string;
  message: string;
}

/** Format probability as percentage with 1 decimal — "85.4%". */
export function formatProbability(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

/** UI tier for visual confidence colour-coding. */
export type ConfidenceTier = "high" | "medium" | "low";

export function confidenceTier(p: number): ConfidenceTier {
  if (p >= 0.7) return "high";
  if (p >= 0.4) return "medium";
  return "low";
}
