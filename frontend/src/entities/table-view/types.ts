import type { FilterValue } from "@/shared/ui/data-table/types";

/**
 * A saved filter/sort/column preset for a user on a specific registry table.
 *
 * Personal views (is_shared=false) are owned by `user_id`.
 * Shared views (is_shared=true) are scoped to `organization_id` and readable
 * by all members of that org; only the owner can edit or delete them.
 * Shared views are reserved for future use — the UI fetches only personal
 * views in the current release.
 */
export interface TableView {
  id: string;
  userId: string;
  tableKey: string;
  name: string;
  filters: Record<string, FilterValue>;
  /** URL-format sort string, e.g. "-amount" or "created_at". Null when unsorted. */
  sort: string | null;
  visibleColumns: readonly string[];
  isShared: boolean;
  organizationId: string | null;
  isDefault: boolean;
  createdAt: string;
  updatedAt: string;
}

/** Payload for creating a new personal or shared view. */
export interface CreateViewInput {
  tableKey: string;
  name: string;
  filters: Record<string, FilterValue>;
  sort: string | null;
  visibleColumns: readonly string[];
  isDefault?: boolean;
  /**
   * When true, creates an organization-shared view. Requires the acting user
   * to hold the `head_of_customs` or `admin` role — otherwise `createView`
   * throws. Personal views (default) are scoped to the acting user only.
   */
  isShared?: boolean;
}

/** Payload for updating an existing view (only provided fields are touched). */
export interface UpdateViewInput {
  name?: string;
  filters?: Record<string, FilterValue>;
  sort?: string | null;
  visibleColumns?: readonly string[];
  isDefault?: boolean;
}
