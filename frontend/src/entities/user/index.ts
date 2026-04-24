// CLIENT-SAFE barrel for @/entities/user. Types + runtime constants only.
// For server-only helpers (getSessionUser, fetchUser*, etc.) use
// @/entities/user/server — those touch the DB via next/headers and can't
// be pulled into client bundles.
export type { SessionUser, RoleCode, UserDepartment } from "./types";
export { ACTIVE_ROLES, ROLE_LABELS_RU } from "./types";
