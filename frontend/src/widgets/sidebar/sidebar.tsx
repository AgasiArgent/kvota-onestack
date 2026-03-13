"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Moon, Sun, Menu, X, PanelLeftClose, PanelLeft } from "lucide-react";
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
}: SidebarProps) {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [viewportMode, setViewportMode] = useState<ViewportMode>("desktop");
  const [mobileOpen, setMobileOpen] = useState(false);

  // Detect viewport mode on mount and resize
  useEffect(() => {
    function handleResize() {
      const mode = getViewportMode();
      setViewportMode(mode);

      if (mode === "mobile") {
        // On mobile, sidebar is an overlay — zero out the content margin
        document.documentElement.setAttribute("data-sidebar-collapsed", "mobile");
      } else if (mode === "tablet") {
        // Auto-collapse on tablet
        setCollapsed(true);
        document.documentElement.setAttribute("data-sidebar-collapsed", "true");
        setMobileOpen(false);
      } else {
        // Desktop — restore expanded sidebar
        setCollapsed(false);
        document.documentElement.setAttribute("data-sidebar-collapsed", "false");
        setMobileOpen(false);
      }
    }

    // Set initial mode
    handleResize();

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Persist dark mode in localStorage
  useEffect(() => {
    const saved = localStorage.getItem("theme") as "light" | "dark" | null;
    const initial = saved === "dark" ? "dark" : "light";
    setTheme(initial);
    document.documentElement.classList.toggle("dark", initial === "dark");
  }, []);

  // Close mobile sidebar on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    document.documentElement.setAttribute(
      "data-sidebar-collapsed",
      String(next)
    );
  }

  function toggleMobileOpen() {
    setMobileOpen((prev) => !prev);
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
    localStorage.setItem("theme", next);
  }

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  const initials = user.email[0]?.toUpperCase() ?? "U";

  // On mobile, the sidebar is either hidden or shown as an overlay
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
      <div className="flex items-center justify-between px-4 h-14 border-b border-border-light">
        {showLabels && (
          <Link
            href="/dashboard"
            prefetch={false}
            className="font-semibold text-lg text-accent"
          >
            Kvota
          </Link>
        )}
        <div className="flex items-center gap-1">
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-md hover:bg-sidebar"
            title="Переключить тему"
          >
            {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          {isMobile ? (
            <button
              onClick={toggleMobileOpen}
              className="p-1.5 rounded-md hover:bg-sidebar"
              title="Закрыть меню"
            >
              <X size={18} />
            </button>
          ) : (
            <button
              onClick={toggleCollapsed}
              className="p-1.5 rounded-md hover:bg-sidebar"
              title={collapsed ? "Развернуть панель" : "Свернуть панель"}
            >
              {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
            </button>
          )}
        </div>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1">
        <nav className="py-2">
          {sections.map((section, idx) => (
            <div key={section.title} className="mb-1">
              {showLabels && (
                <div className="px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-text-subtle">
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
                    prefetch={false}
                    className={cn(
                      "flex items-center gap-3 px-4 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-accent-subtle text-accent"
                        : "text-text hover:bg-sidebar",
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
          ))}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t border-border-light p-3">
        <Link
          href="/profile"
          prefetch={false}
          className="flex items-center gap-3 mb-2"
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
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-text-subtle hover:text-text-muted text-xs w-full px-1"
          title="Выйти из системы"
        >
          <LogOut size={16} />
          {showLabels && <span>Выйти</span>}
        </button>
      </div>
    </aside>
  );

  return (
    <>
      {/* Mobile hamburger button — visible only when sidebar is hidden on mobile */}
      {isMobile && !mobileOpen && (
        <button
          onClick={toggleMobileOpen}
          className="fixed top-3 left-3 z-50 p-2 rounded-md bg-sidebar border border-border-light shadow-sm hover:bg-sidebar/80"
          title="Открыть меню"
        >
          <Menu size={20} />
        </button>
      )}

      {/* Mobile backdrop */}
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
