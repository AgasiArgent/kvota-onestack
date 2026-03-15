import type { LucideIcon } from "lucide-react";
import {
  Inbox,
  PlayCircle,
  Newspaper,
  Send,
  PlusCircle,
  BarChart3,
  Clock,
  Users,
  FileText,
  FileSpreadsheet,
  Building2,
  ClipboardList,
  Phone,
  Building,
  Calendar,
  User,
  MessageSquare,
  GitBranch,
  Settings,
} from "lucide-react";

export interface MenuItem {
  icon: LucideIcon;
  label: string;
  href: string;
  badge?: number;
}

export interface MenuSection {
  title: string;
  items: MenuItem[];
}

interface MenuConfig {
  roles: string[];
  isAdmin: boolean;
  pendingApprovalsCount?: number;
  changelogUnreadCount?: number;
}

export function buildMenuSections(config: MenuConfig): MenuSection[] {
  const {
    roles,
    isAdmin,
    pendingApprovalsCount = 0,
    changelogUnreadCount = 0,
  } = config;
  const hasRole = (...r: string[]) =>
    isAdmin || r.some((role) => roles.includes(role));
  const sections: MenuSection[] = [];

  // === MAIN ===
  const mainItems: MenuItem[] = [
    { icon: Inbox, label: "Мои задачи", href: "/tasks" },
    { icon: PlayCircle, label: "Обучение", href: "/training" },
    {
      icon: Newspaper,
      label: "Обновления",
      href: "/changelog",
      ...(changelogUnreadCount > 0 ? { badge: changelogUnreadCount } : {}),
    },
    { icon: Send, label: "Уведомления", href: "/telegram" },
  ];

  if (hasRole("sales", "sales_manager")) {
    mainItems.push({
      icon: PlusCircle,
      label: "Новый КП",
      href: "/quotes/new",
    });
  }
  if (
    hasRole(
      "top_manager",
      "sales",
      "sales_manager",
      "head_of_sales",
      "procurement",
      "logistics",
      "head_of_logistics",
      "customs",
      "quote_controller",
      "spec_controller",
      "finance"
    )
  ) {
    mainItems.push({
      icon: BarChart3,
      label: "Обзор",
      href: "/dashboard?tab=overview",
    });
  }
  if (hasRole("top_manager")) {
    mainItems.push({
      icon: Clock,
      label: "Согласования",
      href: "/approvals",
      ...(pendingApprovalsCount > 0 ? { badge: pendingApprovalsCount } : {}),
    });
  }
  sections.push({ title: "Главное", items: mainItems });

  // === REGISTRIES ===
  const registries: MenuItem[] = [];
  if (hasRole("sales", "sales_manager", "top_manager", "head_of_sales")) {
    registries.push({
      icon: Users,
      label: "Клиенты",
      href: "/customers",
    });
  }
  registries.push({
    icon: FileText,
    label: "Коммерческие предложения",
    href: "/quotes",
  });
  if (hasRole("sales", "sales_manager")) {
    registries.push({
      icon: FileSpreadsheet,
      label: "PHMB",
      href: "/phmb",
    });
  }
  if (hasRole("procurement")) {
    registries.push({
      icon: Building2,
      label: "Поставщики",
      href: "/suppliers",
    });
    registries.push({
      icon: ClipboardList,
      label: "Очередь PHMB",
      href: "/phmb/procurement",
    });
  }
  if (hasRole("customs", "finance")) {
    registries.push({
      icon: FileText,
      label: "Таможенные декларации",
      href: "/customs/declarations",
    });
  }
  if (hasRole("sales", "sales_manager", "top_manager")) {
    registries.push({
      icon: Phone,
      label: "Журнал звонков",
      href: "/calls",
    });
  }
  if (isAdmin) {
    registries.push({
      icon: Building,
      label: "Юрлица",
      href: "/companies",
    });
  }
  if (registries.length > 0) {
    sections.push({ title: "Реестры", items: registries });
  }

  // === FINANCE ===
  if (hasRole("finance", "top_manager", "currency_controller")) {
    const financeItems: MenuItem[] = [
      {
        icon: FileText,
        label: "Контроль платежей",
        href: "/finance?tab=erps",
      },
      {
        icon: Calendar,
        label: "Календарь",
        href: "/payments/calendar",
      },
    ];
    if (hasRole("currency_controller")) {
      financeItems.push({
        icon: FileText,
        label: "Валютные инвойсы",
        href: "/currency-invoices",
      });
    }
    sections.push({ title: "Финансы", items: financeItems });
  }

  // === ADMIN ===
  if (isAdmin) {
    sections.push({
      title: "Администрирование",
      items: [
        { icon: User, label: "Пользователи", href: "/admin" },
        { icon: MessageSquare, label: "Обращения", href: "/admin/feedback" },
        { icon: GitBranch, label: "Маршрутизация закупок", href: "/admin/procurement-groups" },
        { icon: Settings, label: "Настройки", href: "/settings" },
      ],
    });
  }

  return sections;
}
