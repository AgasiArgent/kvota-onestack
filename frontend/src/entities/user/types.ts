export interface SessionUser {
  id: string;
  email: string;
  orgId: string | null;
  orgName: string;
  roles: string[];
}

// All active roles in the system (from migration 168 + 321)
export const ACTIVE_ROLES = [
  "admin",
  "sales",
  "procurement",
  "procurement_senior",
  "logistics",
  "customs",
  "quote_controller",
  "spec_controller",
  "finance",
  "top_manager",
  "head_of_sales",
  "head_of_procurement",
  "head_of_logistics",
  "head_of_customs",
  "newbie",
] as const;

export type RoleCode = (typeof ACTIVE_ROLES)[number];

// Roles allowed to assign the 'newbie' parking role to other users.
// Testing 2 row 38p2 — admins + every functional head can park inactive
// employees in this role; rank-and-file users cannot.
export const NEWBIE_ASSIGNER_ROLES = [
  "admin",
  "head_of_sales",
  "head_of_procurement",
  "head_of_logistics",
  "head_of_customs",
] as const;

export type NewbieAssignerRole = (typeof NEWBIE_ASSIGNER_ROLES)[number];

/**
 * True when the user has the `newbie` parking role AND no other functional
 * role. A user with `newbie` + any other role behaves like the other role —
 * `newbie` is purely a placeholder for users with no functional access yet.
 */
export function isNewbieOnly(roles: readonly string[]): boolean {
  if (!roles.includes("newbie")) return false;
  return roles.every((r) => r === "newbie");
}

/**
 * True when the caller is permitted to assign the `newbie` role.
 * Used to gate the role-picker option in the admin user-edit sheet.
 */
export function canAssignNewbie(callerRoles: readonly string[]): boolean {
  return callerRoles.some((r) =>
    (NEWBIE_ASSIGNER_ROLES as readonly string[]).includes(r),
  );
}

/**
 * Filters a list of role options for the role picker, hiding `newbie`
 * when the caller cannot assign it and the target user does not
 * already have it. Used by both the user-edit-sheet and the
 * create-user-dialog so the gate stays consistent.
 */
export function filterAssignableRoles<T extends { slug: string }>(
  roles: readonly T[],
  callerRoles: readonly string[],
  options: { memberHasNewbie?: boolean } = {},
): T[] {
  const canAssign = canAssignNewbie(callerRoles);
  const memberHasNewbie = options.memberHasNewbie ?? false;
  return roles.filter((role) => {
    if (role.slug !== "newbie") return true;
    return canAssign || memberHasNewbie;
  });
}

export const ROLE_LABELS_RU: Record<string, string> = {
  admin: "Администратор",
  sales: "Продажи",
  procurement: "Закупки",
  procurement_senior: "Старший закупщик",
  logistics: "Логистика",
  customs: "Таможня",
  quote_controller: "Контроль КП",
  spec_controller: "Контроль спецификаций",
  finance: "Финансы",
  top_manager: "Руководитель",
  head_of_sales: "Руководитель продаж",
  head_of_procurement: "Руководитель закупок",
  head_of_logistics: "Руководитель логистики",
  head_of_customs: "Руководитель таможни",
  training_manager: "Менеджер обучения",
  currency_controller: "Валютный контроль",
  newbie: "Новичок",
};
