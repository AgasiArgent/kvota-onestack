export interface OrgMember {
  user_id: string;
  full_name: string | null;
  email: string;
  roles: { id: string; slug: string; name: string }[];
  telegram_username: string | null;
  joined_at: string;
  status: "active" | "suspended";
  position: string | null;
  sales_group_id: string | null;
  department_id: string | null;
  is_last_admin: boolean;
}

export interface FeedbackItem {
  short_id: string;
  feedback_type: "bug" | "ux" | "suggestion";
  description: string;
  user_name: string | null;
  user_email: string | null;
  status: "new" | "in_progress" | "resolved" | "closed";
  clickup_task_id: string | null;
  created_at: string;
}

export interface FeedbackDetail extends FeedbackItem {
  page_url: string | null;
  screenshot_url: string | null;
  debug_context: Record<string, unknown> | null;
}

export interface RoleOption {
  id: string;
  slug: string;
  name: string;
}

export const ROLE_COLORS: Record<string, string> = {
  admin: "bg-red-100 text-red-700",
  sales: "bg-blue-100 text-blue-700",
  procurement: "bg-amber-100 text-amber-700",
  logistics: "bg-green-100 text-green-700",
  customs: "bg-purple-100 text-purple-700",
  finance: "bg-emerald-100 text-emerald-700",
  top_manager: "bg-rose-100 text-rose-700",
  quote_controller: "bg-cyan-100 text-cyan-700",
  spec_controller: "bg-teal-100 text-teal-700",
  head_of_sales: "bg-indigo-100 text-indigo-700",
  head_of_procurement: "bg-orange-100 text-orange-700",
  head_of_logistics: "bg-lime-100 text-lime-700",
};

export const FEEDBACK_TYPE_LABELS: Record<string, string> = {
  bug: "Ошибка",
  ux: "UX",
  suggestion: "Предложение",
};

export const FEEDBACK_TYPE_COLORS: Record<string, string> = {
  bug: "bg-red-100 text-red-700",
  ux: "bg-blue-100 text-blue-700",
  suggestion: "bg-green-100 text-green-700",
};

export const FEEDBACK_STATUS_LABELS: Record<string, string> = {
  new: "Новое",
  in_progress: "В работе",
  resolved: "Решено",
  closed: "Закрыто",
};

export const FEEDBACK_STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-100 text-blue-700",
  in_progress: "bg-amber-100 text-amber-700",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-slate-100 text-slate-700",
};

export interface CreateUserPayload {
  email: string;
  password: string;
  full_name: string;
  role_slugs: string[];
  position?: string;
  sales_group_id?: string | null;
  department_id?: string | null;
}

export interface UpdateUserPayload {
  full_name?: string;
  position?: string;
  sales_group_id?: string | null;
  department_id?: string | null;
}
