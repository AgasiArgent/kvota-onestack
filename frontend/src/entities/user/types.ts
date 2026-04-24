export interface SessionUser {
  id: string;
  email: string;
  orgId: string | null;
  orgName: string;
  roles: string[];
}

// All active roles in the system (from migration 168)
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
] as const;

export type RoleCode = (typeof ACTIVE_ROLES)[number];

export interface UserDepartment {
  roles: Array<{ name: string; slug: string }>;
  supervisor: { full_name: string } | null;
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
  training_manager: "Менеджер обучения",
  currency_controller: "Валютный контроль",
};
