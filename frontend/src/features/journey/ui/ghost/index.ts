/**
 * Public surface of the ghost CRUD feature.
 */

export { GhostCreateDialog } from "./ghost-create-dialog";
export { GhostEditDialog } from "./ghost-edit-dialog";
export { GhostDeleteConfirm } from "./ghost-delete-confirm";
export { GhostActionMenu } from "./ghost-action-menu";
export { GhostListManager } from "./ghost-list-manager";
export { deriveGhostSlug, validateGhostSlug } from "./_ghost-slug";
export {
  buildGhostPayload,
  classifyGhostWriteError,
  type GhostPayloadInput,
  type GhostWriteErrorKind,
  type GhostWriteErrorInfo,
} from "./_ghost-dialog-helpers";
