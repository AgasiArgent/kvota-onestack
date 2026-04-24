/**
 * Public surface of the pin-overlay feature (Tasks 21 + 22).
 */

export { PinCreator } from "./pin-creator";
export { DomPicker } from "./dom-picker";
export { AnnotatedScreen } from "./annotated-screen";
export { PinBadge } from "./pin-badge";
export { PinPopover } from "./pin-popover";
export {
  buildPinPayload,
  validatePinForm,
  classifyPinCreateError,
  EMPTY_PIN_FORM,
  type PinFormValues,
  type PinFormValidation,
  type PinCreateErrorInfo,
  type PinCreateErrorKind,
  type PinInsert,
} from "./_pin-helpers";
export {
  computePinAbsolutePosition,
  partitionPinsByBbox,
  classifyPinBadgeState,
  type PinBadgeState,
  type AbsRect,
  type RelRect,
  type ContainerSize,
} from "./_overlay-math";
