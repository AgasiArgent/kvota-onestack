"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Moon, Sun, Menu } from "lucide-react";
import { createClient } from "@/shared/lib/supabase/client";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { SessionUser } from "@/entities/user";
import { buildMenuSections } from "./sidebar-menu";

interface SidebarProps {
  user: SessionUser;
  pendingApprovalsCount?: number;
  changelogUnreadCount?: number;
}

export function Sidebar({
  user,
  pendingApprovalsCount = 0,
  changelogUnreadCount = 0,
}: SidebarProps) {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    document.documentElement.setAttribute(
      "data-sidebar-collapsed",
      String(next)
    );
  }

  const isAdmin =
    user.roles.includes("admin") || user.roles.includes("training_manager");
  const sections = buildMenuSections({
    roles: user.roles,
    isAdmin,
    pendingApprovalsCount,
    changelogUnreadCount,
  });

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
  }

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  const initials = user.email[0]?.toUpperCase() ?? "U";

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 h-screen bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700 flex flex-col z-50 transition-[width] duration-200",
        collapsed ? "w-[60px]" : "w-[260px]"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-14 border-b border-slate-200 dark:border-slate-700">
        {!collapsed && (
          <Link
            href="/dashboard"
            className="font-semibold text-lg text-blue-600"
          >
            Kvota
          </Link>
        )}
        <div className="flex items-center gap-1">
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800"
            title="Переключить тему"
          >
            {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          <button
            onClick={toggleCollapsed}
            className="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800"
            title="Свернуть панель"
          >
            <Menu size={18} />
          </button>
        </div>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1">
        <nav className="py-2">
          {sections.map((section, idx) => (
            <div key={section.title} className="mb-1">
              {!collapsed && (
                <div className="px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  {section.title}
                </div>
              )}
              {section.items.map((item) => {
                const hrefPath = item.href.split("?")[0];
                const isActive =
                  pathname === hrefPath ||
                  (hrefPath !== "/" && pathname.startsWith(hrefPath));
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href + item.label}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 px-4 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400"
                        : "text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800",
                      collapsed && "justify-center px-0"
                    )}
                    title={collapsed ? item.label : undefined}
                  >
                    <Icon size={20} className="shrink-0" />
                    {!collapsed && (
                      <span className="truncate">{item.label}</span>
                    )}
                    {!collapsed && item.badge && (
                      <Badge
                        variant="destructive"
                        className="ml-auto text-[10px] px-1.5 py-0 min-w-[18px] text-center"
                      >
                        {item.badge}
                      </Badge>
                    )}
                  </Link>
                );
              })}
              {idx < sections.length - 1 && <Separator className="my-1" />}
            </div>
          ))}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t border-slate-200 dark:border-slate-700 p-3">
        <Link href="/profile" className="flex items-center gap-3 mb-2">
          <Avatar className="h-8 w-8">
            <AvatarFallback className="bg-blue-100 text-blue-700 text-sm">
              {initials}
            </AvatarFallback>
          </Avatar>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-sm truncate">{user.email}</p>
              <p className="text-xs text-blue-500">Профиль</p>
            </div>
          )}
        </Link>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-slate-400 hover:text-slate-600 text-xs w-full px-1"
          title="Выйти из системы"
        >
          <LogOut size={16} />
          {!collapsed && <span>Выйти</span>}
        </button>
      </div>
    </aside>
  );
}
