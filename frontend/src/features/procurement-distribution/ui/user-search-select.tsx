"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProcurementUserWorkload } from "../model/types";

interface Props {
  users: ProcurementUserWorkload[];
  value: string;
  onValueChange: (userId: string) => void;
  disabled?: boolean;
}

export function UserSearchSelect({
  users,
  value,
  onValueChange,
  disabled = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedUser = users.find((u) => u.user_id === value);

  const filtered = search
    ? users.filter((u) =>
        (u.full_name ?? "").toLowerCase().includes(search.toLowerCase())
      )
    : users;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(userId: string) {
    onValueChange(userId);
    setOpen(false);
    setSearch("");
  }

  function handleClear(e: React.MouseEvent) {
    e.stopPropagation();
    onValueChange("");
    setSearch("");
  }

  function handleTriggerClick() {
    if (disabled) return;
    setOpen(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Trigger */}
      <button
        type="button"
        onClick={handleTriggerClick}
        disabled={disabled}
        className={cn(
          "flex w-full items-center justify-between gap-1 rounded-lg border border-input bg-transparent py-2 px-2.5 text-sm h-8 transition-colors",
          "hover:bg-accent/5 disabled:cursor-not-allowed disabled:opacity-50",
          open && "border-ring ring-3 ring-ring/50"
        )}
      >
        <span className="truncate text-left flex-1">
          {selectedUser ? selectedUser.full_name : (
            <span className="text-muted-foreground">Закупщик</span>
          )}
        </span>
        {value ? (
          <X
            size={14}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            onClick={handleClear}
          />
        ) : (
          <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute top-full left-0 z-[300] mt-1 w-full min-w-[220px] rounded-lg border bg-popover shadow-md">
          <div className="p-1.5">
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск..."
              className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none focus:border-ring"
            />
          </div>
          <div className="max-h-[200px] overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <div className="py-2 px-2 text-sm text-muted-foreground text-center">
                Не найдено
              </div>
            ) : (
              filtered.map((u) => (
                <button
                  key={u.user_id}
                  type="button"
                  onClick={() => handleSelect(u.user_id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm cursor-default",
                    "hover:bg-accent hover:text-accent-foreground",
                    u.user_id === value && "bg-accent/10 font-medium"
                  )}
                >
                  <span className="truncate">
                    {u.full_name ?? u.user_id}
                  </span>
                  <span className="ml-2 text-xs text-muted-foreground shrink-0">
                    {u.active_quotes}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
