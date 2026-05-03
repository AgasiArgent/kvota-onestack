import type { QuoteStep } from "./types";

/**
 * Default `step` for the quote detail page when the URL has no `?step=` param.
 *
 * The mapping is workflow-status-aware so that landing on a quote without an
 * explicit step parameter takes the user to the step that matches the quote's
 * current stage, not a hardcoded "Заявка". This fixes two recurring UX bugs:
 *  - clicking the IDN from /procurement/distribution dropped the user on
 *    «Заявка» instead of «Закупки» (where pending_procurement quotes belong);
 *  - clicking «Закрыть документы» on the sticky header navigated to bare
 *    `/quotes/{id}` and inherited the same wrong default.
 *
 * Mapping (per product spec):
 *   draft, pending_sales_review                          → sales       (Заявка)
 *   pending_procurement, procurement_complete            → procurement (Закупки)
 *   pending_logistics_and_customs                        → logistics
 *   pending_spec_control                                 → control
 *   spec_signed, approved, deal                          → specification
 *   cancelled (and any unknown status)                   → sales       (fallback)
 *
 * NOTE: This map is INTENTIONALLY DIFFERENT from STATUS_TO_STEP in types.ts
 * (which controls rail highlighting). The semantic distinction:
 *   - STATUS_TO_STEP: where the work CURRENTLY IS (highlight indicator)
 *   - STATUS_DEFAULT_STEP: where to LAND THE USER for action (UX target)
 *
 * Examples of intentional divergence:
 *   pending_sales_review: rail highlights "calculation" (work is there),
 *     but default lands user on "sales" (where they need to ACT next).
 *   procurement_complete: rail highlights "calculation" (next step),
 *     but default lands on "procurement" (where the КП is closed).
 *
 * When adding a new workflow_status: update BOTH maps consciously.
 */
const STATUS_DEFAULT_STEP: Record<string, QuoteStep> = {
  draft: "sales",
  pending_sales_review: "sales",
  pending_procurement: "procurement",
  procurement_complete: "procurement",
  pending_logistics_and_customs: "logistics",
  pending_spec_control: "control",
  spec_signed: "specification",
  approved: "specification",
  deal: "specification",
  cancelled: "sales",
};

/**
 * Resolve the default `step` for a quote.
 *
 * @param workflowStatus  current `quotes.workflow_status` value
 * @param allowedSteps    steps the user is permitted to view (from
 *                        `ROLE_ALLOWED_STEPS`). When the mapped default isn't
 *                        in this list, fall back to the first allowed step so
 *                        we never render a step the user can't access.
 *                        Pass `undefined` (or omit) to skip permission checks.
 */
export function getDefaultStep(
  workflowStatus: string | null | undefined,
  allowedSteps?: readonly QuoteStep[],
): QuoteStep {
  if (workflowStatus && !(workflowStatus in STATUS_DEFAULT_STEP)) {
    console.warn(
      `[getDefaultStep] Unknown workflow_status "${workflowStatus}" — falling back to "sales". ` +
      `Add it to STATUS_DEFAULT_STEP and STATUS_TO_STEP if it's a new enum value.`
    );
  }
  const mapped = STATUS_DEFAULT_STEP[workflowStatus ?? ""] ?? "sales";

  if (!allowedSteps || allowedSteps.length === 0) return mapped;
  if (allowedSteps.includes(mapped)) return mapped;

  return allowedSteps[0];
}
