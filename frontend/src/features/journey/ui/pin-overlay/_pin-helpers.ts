/**
 * Pure helpers for the Task 21 pin-creation UI.
 *
 * Isolated so behaviour is testable without a DOM (the frontend workspace
 * ships no jsdom). The dialog component orchestrates toasts + mutations on
 * top of these.
 *
 * Reqs: 8.1 (pin fields), 8.2 (training_step_order required for training),
 * 8.5 (manual selector or DOM picker).
 */

import type {
  JourneyNodeId,
  JourneyPin,
  PinMode,
} from "@/entities/journey";

// ---------------------------------------------------------------------------
// Form model
// ---------------------------------------------------------------------------

export interface PinFormValues {
  readonly mode: PinMode;
  readonly selector: string;
  readonly expected_behavior: string;
  readonly training_step_order: number | null;
  readonly linked_story_ref: string | null;
}

export const EMPTY_PIN_FORM: PinFormValues = {
  mode: "qa",
  selector: "",
  expected_behavior: "",
  training_step_order: null,
  linked_story_ref: null,
};

// ---------------------------------------------------------------------------
// Payload construction
// ---------------------------------------------------------------------------

/**
 * Shape accepted by `createPin` in `entities/journey/queries.ts` — omits the
 * server-computed position fields (`last_rel_*`, `last_position_update`,
 * `selector_broken`) and metadata columns (`id`, `created_at`).
 */
export type PinInsert = Omit<
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

export interface BuildPinPayloadInput {
  readonly form: PinFormValues;
  readonly node_id: JourneyNodeId;
  readonly created_by: string;
}

export function buildPinPayload(input: BuildPinPayloadInput): PinInsert {
  const { form, node_id, created_by } = input;
  return {
    node_id,
    selector: form.selector,
    expected_behavior: form.expected_behavior,
    mode: form.mode,
    // Req 8.2: QA pins must not carry a training order, even if the form
    // field retained a stale value when the user toggled modes.
    training_step_order:
      form.mode === "training" ? form.training_step_order : null,
    linked_story_ref: form.linked_story_ref,
    created_by,
  };
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

export interface PinFormValidation {
  readonly valid: boolean;
  readonly errors: Record<string, string>;
}

/**
 * Approximate CSS-selector sniff: a leading `[`, `.`, `#`, `:` or an ASCII
 * letter (tag name). Good enough to reject free-form prose that the user
 * typed by accident — not a full CSS parser.
 */
const SELECTOR_LEAD = /^([[.#:]|[a-zA-Z])/;
/** Selector-ish markers that a multi-token CSS selector must contain. */
const SELECTOR_MARKERS = /[[\]#.:>+~*]/;

function looksLikeSelector(raw: string): boolean {
  if (!SELECTOR_LEAD.test(raw)) return false;
  // Multi-token selectors (e.g. `div > button.foo`) are fine only if they
  // contain at least one CSS marker. Plain prose with spaces (`just some
  // text`) matches `SELECTOR_LEAD` but has no marker — reject it.
  if (/\s/.test(raw) && !SELECTOR_MARKERS.test(raw)) return false;
  return true;
}

export function validatePinForm(form: PinFormValues): PinFormValidation {
  const errors: Record<string, string> = {};

  const trimmedSelector = form.selector.trim();
  if (trimmedSelector.length === 0) {
    errors.selector = "Обязательное поле";
  } else if (!looksLikeSelector(trimmedSelector)) {
    errors.selector = "Не похоже на CSS-селектор";
  }

  if (form.expected_behavior.trim().length === 0) {
    errors.expected_behavior = "Обязательное поле";
  }

  if (form.mode === "training") {
    if (
      form.training_step_order === null ||
      form.training_step_order === undefined ||
      form.training_step_order <= 0
    ) {
      errors.training_step_order = "Укажите порядок шага";
    }
  }

  return { valid: Object.keys(errors).length === 0, errors };
}

// ---------------------------------------------------------------------------
// Error classification
// ---------------------------------------------------------------------------

export type PinCreateErrorKind =
  | "PERMISSION_DENIED"
  | "FK_VIOLATION"
  | "UNIQUE_VIOLATION"
  | "UNKNOWN";

export interface PinCreateErrorInfo {
  readonly kind: PinCreateErrorKind;
  readonly userMessage: string;
}

interface MaybePgError {
  readonly code?: string;
  readonly message?: string;
}

export function classifyPinCreateError(err: unknown): PinCreateErrorInfo {
  if (err === null || err === undefined) {
    return {
      kind: "UNKNOWN",
      userMessage: "Не удалось создать пин. Попробуйте ещё раз.",
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
      userMessage: "Недостаточно прав для создания пина.",
    };
  }

  if (code === "23503" || message.includes("foreign key")) {
    return {
      kind: "FK_VIOLATION",
      userMessage: "Узел не найден. Обновите страницу и попробуйте снова.",
    };
  }

  if (code === "23505" || message.includes("duplicate key")) {
    return {
      kind: "UNIQUE_VIOLATION",
      userMessage: "Такой пин уже существует на этом узле.",
    };
  }

  return {
    kind: "UNKNOWN",
    userMessage:
      e.message && e.message.length > 0
        ? e.message
        : "Не удалось создать пин. Попробуйте ещё раз.",
  };
}
