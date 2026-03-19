"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu, X, PanelLeftClose, PanelLeft, ChevronDown } from "lucide-react";
import { createClient } from "@/shared/lib/supabase/client";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { SessionUser } from "@/entities/user";
import { buildMenuSections, buildPhmbMenuSections } from "./sidebar-menu";
import type { AppContext } from "@/shared/lib/app-context";

interface SidebarProps {
  user: SessionUser;
  pendingApprovalsCount?: number;
  changelogUnreadCount?: number;
  appContext?: AppContext;
}

type ViewportMode = "desktop" | "tablet" | "mobile";

function getViewportMode(): ViewportMode {
  if (typeof window === "undefined") return "desktop";
  const width = window.innerWidth;
  if (width <= 640) return "mobile";
  if (width <= 768) return "tablet";
  return "desktop";
}

export function Sidebar({
  user,
  pendingApprovalsCount = 0,
  changelogUnreadCount = 0,
  appContext = "main",
}: SidebarProps) {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [viewportMode, setViewportMode] = useState<ViewportMode>("desktop");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set();
    try {
      const saved = localStorage.getItem("sidebar-collapsed-sections");
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch { return new Set(); }
  });

  const toggleSection = useCallback((title: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      try { localStorage.setItem("sidebar-collapsed-sections", JSON.stringify([...next])); } catch {}
      return next;
    });
  }, []);

  useEffect(() => {
    function handleResize() {
      const mode = getViewportMode();
      setViewportMode(mode);

      if (mode === "mobile") {
        document.documentElement.setAttribute("data-sidebar-collapsed", "mobile");
      } else if (mode === "tablet") {
        setCollapsed(true);
        document.documentElement.setAttribute("data-sidebar-collapsed", "true");
        setMobileOpen(false);
      } else {
        setCollapsed(false);
        document.documentElement.setAttribute("data-sidebar-collapsed", "false");
        setMobileOpen(false);
      }
    }

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    document.documentElement.setAttribute("data-sidebar-collapsed", String(next));
  }

  function toggleMobileOpen() {
    setMobileOpen((prev) => !prev);
  }

  const isAdmin =
    user.roles.includes("admin") || user.roles.includes("training_manager");
  const menuBuilder = appContext === "phmb" ? buildPhmbMenuSections : buildMenuSections;
  const sections = menuBuilder({
    roles: user.roles,
    isAdmin,
    pendingApprovalsCount,
    changelogUnreadCount,
  });

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  const initials = user.email[0]?.toUpperCase() ?? "U";

  const isMobile = viewportMode === "mobile";
  const isIconOnly = collapsed || viewportMode === "tablet";
  const showLabels = !isIconOnly || isMobile;

  const sidebarContent = (
    <aside
      className={cn(
        "fixed left-0 top-0 h-screen bg-sidebar border-r border-border-light flex flex-col z-50 transition-[width] duration-200",
        isMobile ? "w-[260px]" : isIconOnly ? "w-[60px]" : "w-[260px]",
        isMobile && !mobileOpen && "hidden"
      )}
    >
      {/* Header */}
      <div className={cn(
        "flex items-center h-14 border-b border-border-light",
        showLabels ? "justify-between px-4" : "justify-center"
      )}>
        {showLabels && (
          <div className="flex items-center gap-2">
            <Link
              href={appContext === "phmb" ? "/phmb" : "/quotes"}
              prefetch={false}
              className="font-semibold text-lg text-accent"
            >
              {appContext === "phmb" ? "PHMB" : "Kvota"}
            </Link>
            <a
              href={appContext === "phmb" ? "https://app.kvotaflow.ru" : "https://phmb.kvotaflow.ru"}
              className="px-1.5 py-0.5 text-[10px] font-medium rounded border border-border-light text-text-muted hover:text-accent hover:border-accent transition-colors"
              title={appContext === "phmb" ? "Перейти в основное приложение" : "Перейти в PHMB"}
            >
              {appContext === "phmb" ? "Main" : "PHMB"}
            </a>
          </div>
        )}
        {isMobile && (
          <button
            onClick={toggleMobileOpen}
            className="p-1.5 rounded-md hover:bg-background"
            title="Закрыть меню"
          >
            <X size={18} />
          </button>
        )}
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 overflow-hidden">
        <nav className="py-2">
          {sections.map((section, idx) => {
            const isSectionCollapsed = collapsedSections.has(section.title);
            return (
            <div key={section.title} className="mb-1">
              {showLabels && (
                <button
                  type="button"
                  onClick={() => toggleSection(section.title)}
                  className="w-full flex items-center justify-between px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-text-subtle hover:text-text-muted transition-colors"
                >
                  <span>{section.title}</span>
                  <ChevronDown
                    size={12}
                    className={cn(
                      "transition-transform duration-200",
                      isSectionCollapsed && "-rotate-90"
                    )}
                  />
                </button>
              )}
              {!isSectionCollapsed && section.items.map((item) => {
                const hrefPath = item.href.split("?")[0];
                const isActive =
                  pathname === hrefPath ||
                  (hrefPath !== "/" && pathname.startsWith(hrefPath));
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href + item.label}
                    href={item.href}
                    prefetch={false}
                    className={cn(
                      "flex items-center gap-3 px-4 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-accent-subtle text-accent"
                        : "text-text hover:bg-background",
                      !showLabels && "justify-center px-0"
                    )}
                    title={!showLabels ? item.label : undefined}
                  >
                    <Icon size={20} className="shrink-0" />
                    {showLabels && (
                      <span className="truncate">{item.label}</span>
                    )}
                    {showLabels && item.badge && (
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
            );
          })}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t border-border-light p-3 space-y-2">
        <Link
          href="/profile"
          prefetch={false}
          className="flex items-center gap-3"
        >
          <Avatar className="h-8 w-8">
            <AvatarFallback className="bg-accent-subtle text-accent text-sm">
              {initials}
            </AvatarFallback>
          </Avatar>
          {showLabels && (
            <div className="min-w-0">
              <p className="text-sm truncate">{user.email}</p>
              <p className="text-xs text-accent">Профиль</p>
            </div>
          )}
        </Link>
        <div className={cn(
          "flex items-center",
          showLabels ? "justify-between" : "justify-center gap-1"
        )}>
          {showLabels ? (
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 text-text-subtle hover:text-text-muted text-xs px-1"
              title="Выйти из системы"
            >
              <LogOut size={16} />
              <span>Выйти</span>
            </button>
          ) : (
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-md text-text-subtle hover:text-text-muted hover:bg-background"
              title="Выйти из системы"
            >
              <LogOut size={16} />
            </button>
          )}
          {!isMobile && (
            <button
              onClick={toggleCollapsed}
              className="p-1.5 rounded-md text-text-subtle hover:text-text-muted hover:bg-background"
              title={collapsed ? "Развернуть панель" : "Свернуть панель"}
            >
              {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
            </button>
          )}
        </div>
      </div>
    </aside>
  );

  return (
    <>
      {isMobile && !mobileOpen && (
        <button
          onClick={toggleMobileOpen}
          className="fixed top-3 left-3 z-50 p-2 rounded-md bg-sidebar border border-border-light shadow-sm hover:bg-sidebar/80"
          title="Открыть меню"
        >
          <Menu size={20} />
        </button>
      )}

      {isMobile && mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50"
          onClick={toggleMobileOpen}
          aria-hidden="true"
        />
      )}

      {sidebarContent}
    </>
  );
}
