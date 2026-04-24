import "server-only";

// Server-only barrel for @/entities/user. Pulls next/headers through the
// Supabase server client — NEVER import this from a client component.
// Client components should use @/entities/user (types + constants only).
export { getSessionUser } from "./get-session-user";
export {
  fetchUserDepartment,
  fetchUserSalesGroupId,
  fetchProcurementWorkload,
} from "./queries";
