"use client";

import { MessageCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatFabProps {
  unreadCount: number;
  onClick: () => void;
}

export function ChatFab({ unreadCount, onClick }: ChatFabProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "fixed bottom-6 right-6 z-40",
        "flex items-center justify-center w-14 h-14 rounded-full",
        "bg-primary text-primary-foreground shadow-lg",
        "hover:bg-primary/90 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      )}
      aria-label="Открыть чат"
    >
      <MessageCircle className="w-6 h-6" />
      {unreadCount > 0 && (
        <span
          className={cn(
            "absolute -top-1 -right-1 flex items-center justify-center",
            "min-w-5 h-5 px-1 rounded-full",
            "bg-destructive text-destructive-foreground text-xs font-medium",
            "pointer-events-none"
          )}
        >
          {unreadCount > 99 ? "99+" : unreadCount}
        </span>
      )}
    </button>
  );
}
