/**
 * Pure helpers for the Task 27 training-section UI.
 *
 * Kept side-effect-free so behaviour can be tested without a DOM. The
 * interactive editor (`training-editor.tsx`) and presentational section
 * (`training-section.tsx`) orchestrate toasts + mutations on top of these.
 *
 * Reqs: 5.4 (training steps rendered as ordered markdown blocks, ordered by
 * `training_step_order`), 8.2 (training pins require a non-null
 * `training_step_order`), 12.10 (CUD restricted to admin + head_of_*).
 */

import {
  canEditTraining as canEditTrainingAccess,
  type JourneyNodeId,
  type JourneyPin,
  type RoleSlug,
} from "@/entities/journey";

// ---------------------------------------------------------------------------
// Ordering
// ---------------------------------------------------------------------------

/**
 * Return only `mode="training"` pins, ordered by `training_step_order`
 * ascending. Pins with a null order are appended in insertion order so the
 * UI never silently hides newly-created steps that are mid-edit.
 *
 * Stable sort semantics: `Array.prototype.sort` is specced as stable in
 * ES2019+, so equal orders preserve their input order.
 */
export function orderTrainingSteps(
  pins: readonly JourneyPin[]
): readonly JourneyPin[] {
  const training = pins.filter((p) => p.mode === "training");
  const withOrder = training.filter((p) => p.training_step_order !== null);
  const withoutOrder = training.filter((p) => p.training_step_order === null);
  const sorted = withOrder.slice().sort((a, b) => {
    const ao = a.training_step_order as number;
    const bo = b.training_step_order as number;
    return ao - bo;
  });
  return [...sorted, ...withoutOrder];
}

// ---------------------------------------------------------------------------
// Payload construction
// ---------------------------------------------------------------------------

/**
 * Shape accepted by `createPin` in `entities/journey/queries.ts` — omits the
 * server-computed position fields and metadata columns. A mirror of
 * `pin-overlay/_pin-helpers.ts::PinInsert`, duplicated here rather than
 * cross-imported because the training editor does not share validation
 * logic (e.g. selector validation is optional for markdown steps).
 */
export type TrainingStepInsert = Omit<
  JourneyPin,
  | "id"
  | "created_at"
  | "last_rel_x"
  | "last_rel_y"
  | "last_rel_width"
  | "last_rel_height"
  | "last_position_update"
  | "selector_broken"
>;

export interface BuildTrainingStepInput {
  readonly stepOrder: number;
  readonly expected_behavior: string;
  readonly selector: string;
  readonly node_id: JourneyNodeId;
  readonly created_by: string;
  readonly linked_story_ref?: string | null;
}

/**
 * Build the `createPin` payload for a training step. Enforces Req 8.2 by
 * always emitting `mode="training"` and a non-null `training_step_order`.
 */
export function buildTrainingStepPayload(
  input: BuildTrainingStepInput
): TrainingStepInsert {
  const {
    stepOrder,
    expected_behavior,
    selector,
    node_id,
    created_by,
    linked_story_ref = null,
  } = input;
  return {
    node_id,
    selector,
    expected_behavior,
    mode: "training",
    training_step_order: stepOrder,
    linked_story_ref,
    created_by,
  };
}

// ---------------------------------------------------------------------------
// Reorder
// ---------------------------------------------------------------------------

export interface ReorderedStep {
  readonly id: string;
  readonly training_step_order: number;
}

/**
 * Compute a list of `{id, training_step_order}` tuples describing the new
 * contiguous 1..N ordering after moving the item at `fromIndex` to
 * `toIndex`. Returns the full sequence (not just the diff) so the caller
 * can apply batched updates without having to detect which rows moved.
 *
 * Only rows whose order actually changed are included — this lets the
 * caller avoid no-op UPDATE round-trips.
 *
 * Pure: does not mutate `steps`.
 */
export function computeReorderedSteps(
  steps: readonly JourneyPin[],
  fromIndex: number,
  toIndex: number
): readonly ReorderedStep[] {
  if (fromIndex === toIndex) return [];
  if (fromIndex < 0 || fromIndex >= steps.length) return [];
  if (toIndex < 0 || toIndex >= steps.length) return [];

  const reordered = steps.slice();
  const [moved] = reordered.splice(fromIndex, 1);
  reordered.splice(toIndex, 0, moved);

  const changes: ReorderedStep[] = [];
  reordered.forEach((pin, idx) => {
    const newOrder = idx + 1;
    if (pin.training_step_order !== newOrder) {
      changes.push({ id: pin.id, training_step_order: newOrder });
    }
  });
  return changes;
}

// ---------------------------------------------------------------------------
// Error classification
// ---------------------------------------------------------------------------

export type TrainingEditorErrorKind =
  | "PERMISSION_DENIED"
  | "VALIDATION"
  | "FK_VIOLATION"
  | "UNKNOWN";

export interface TrainingEditorErrorInfo {
  readonly kind: TrainingEditorErrorKind;
  readonly userMessage: string;
}

interface MaybePgError {
  readonly code?: string;
  readonly message?: string;
}

export function classifyTrainingEditorError(
  err: unknown
): TrainingEditorErrorInfo {
  if (err === null || err === undefined) {
    return {
      kind: "UNKNOWN",
      userMessage: "Не удалось сохранить. Попробуйте ещё раз.",
    };
  }
  const e = err as MaybePgError;
  const code = e.code ?? "";
  const message = (e.message ?? "").toLowerCase();

  if (
    code === "42501" ||
    message.includes("row-level security") ||
    message.includes("permission denied")
  ) {
    return {
      kind: "PERMISSION_DENIED",
      userMessage: "Недостаточно прав для изменения шагов обучения.",
    };
  }

  if (code === "23514" || message.includes("check constraint")) {
    return {
      kind: "VALIDATION",
      userMessage: "Неверные данные шага. Проверьте поля и попробуйте ещё раз.",
    };
  }

  if (code === "23503" || message.includes("foreign key")) {
    return {
      kind: "FK_VIOLATION",
      userMessage: "Узел не найден. Обновите страницу и попробуйте снова.",
    };
  }

  return {
    kind: "UNKNOWN",
    userMessage:
      e.message && e.message.length > 0
        ? e.message
        : "Не удалось сохранить. Попробуйте ещё раз.",
  };
}

// ---------------------------------------------------------------------------
// ACL — re-exported next-available-step helper
// ---------------------------------------------------------------------------

/**
 * The next `training_step_order` for a new step — one more than the current
 * max, or 1 if no steps exist yet.
 */
export function nextTrainingStepOrder(
  pins: readonly JourneyPin[]
): number {
  const orders = pins
    .filter((p) => p.mode === "training" && p.training_step_order !== null)
    .map((p) => p.training_step_order as number);
  if (orders.length === 0) return 1;
  return Math.max(...orders) + 1;
}

/**
 * Role-gate for the training editor (Req 12.10) — admin + each head_of_*.
 *
 * Re-exported from `entities/journey/access.ts` so tests in this module can
 * import it alongside the other training helpers. The canonical definition
 * lives in the entity slice's access module; every other surface imports
 * from there.
 */
export function canEditTraining(
  heldRoles: readonly RoleSlug[]
): boolean {
  return canEditTrainingAccess(heldRoles);
}
