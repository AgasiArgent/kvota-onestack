import type { LucideIcon } from "lucide-react";
import {
  PlayCircle,
  Newspaper,
  PlusCircle,
  BarChart3,
  Clock,
  Users,
  FileText,
  Building2,
  ClipboardList,
  Building,
  MapPin,
  Calendar,
  User,
  MessageSquare,
  MessageCircle,
  GitBranch,
  Settings,
  SplitSquareHorizontal,
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
  unassignedDistributionCount?: number;
}

export function buildMenuSections(config: MenuConfig): MenuSection[] {
  const {
    roles,
    isAdmin,
    pendingApprovalsCount = 0,
    changelogUnreadCount = 0,
    unassignedDistributionCount = 0,
  } = config;
  const hasRole = (...r: string[]) =>
    isAdmin || r.some((role) => roles.includes(role));
  const sections: MenuSection[] = [];

  // === MAIN ===
  const mainItems: MenuItem[] = [
    { icon: PlayCircle, label: "Обучение", href: "/training" },
    { icon: MessageCircle, label: "Сообщения", href: "/messages" },
    {
      icon: Newspaper,
      label: "Обновления",
      href: "/changelog",
      ...(changelogUnreadCount > 0 ? { badge: changelogUnreadCount } : {}),
    },
  ];

  if (hasRole("sales", "sales_manager")) {
    mainItems.push({
      icon: PlusCircle,
      label: "Новый КП",
      href: "/quotes?create=true",
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
  if (hasRole("head_of_procurement")) {
    mainItems.push({
      icon: SplitSquareHorizontal,
      label: "Распределение",
      href: "/procurement/distribution",
      ...(unassignedDistributionCount > 0
        ? { badge: unassignedDistributionCount }
        : {}),
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
  if (hasRole("procurement")) {
    registries.push({
      icon: Building2,
      label: "Поставщики",
      href: "/suppliers",
    });
    registries.push({
      icon: ClipboardList,
      label: "Позиции",
      href: "/positions",
    });
  }
  if (hasRole("finance", "procurement")) {
    registries.push({
      icon: Building,
      label: "Юрлица",
      href: "/companies",
    });
  }
  if (hasRole("logistics", "customs", "procurement")) {
    registries.push({
      icon: MapPin,
      label: "Локации",
      href: "/locations",
    });
  }
  if (hasRole("customs", "finance")) {
    registries.push({
      icon: FileText,
      label: "Таможенные декларации",
      href: "/customs/declarations",
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
  if (isAdmin || hasRole("head_of_procurement")) {
    const adminItems: MenuItem[] = [];
    if (isAdmin) {
      adminItems.push(
        { icon: User, label: "Пользователи", href: "/admin/users" },
        { icon: MessageSquare, label: "Обращения", href: "/admin/feedback" },
      );
    }
    adminItems.push({
      icon: GitBranch,
      label: "Маршруты закупок",
      href: "/admin/routing",
    });
    if (isAdmin) {
      adminItems.push({
        icon: Settings,
        label: "Настройки",
        href: "/settings",
      });
    }
    sections.push({ title: "Администрирование", items: adminItems });
  }

  return sections;
}

export function buildPhmbMenuSections(config: MenuConfig): MenuSection[] {
  const { roles, isAdmin } = config;
  const hasRole = (...r: string[]) =>
    isAdmin || r.some((role) => roles.includes(role));
  const sections: MenuSection[] = [];

  // === PHMB MAIN ===
  const phmbItems: MenuItem[] = [
    { icon: FileText, label: "Реестр КП", href: "/phmb" },
  ];

  if (hasRole("procurement")) {
    phmbItems.push({
      icon: ClipboardList,
      label: "Очередь закупок",
      href: "/phmb/procurement",
    });
  }
  if (hasRole("sales", "sales_manager")) {
    phmbItems.push({
      icon: Settings,
      label: "Настройки",
      href: "/phmb/settings",
    });
  }
  sections.push({ title: "PHMB", items: phmbItems });

  return sections;
}
