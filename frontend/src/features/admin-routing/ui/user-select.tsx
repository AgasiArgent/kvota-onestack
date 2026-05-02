"use client";

import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { fetchProcurementUsers } from "../api/routing-api";
import type { ProcurementUser } from "../model/types";

/**
 * Searchable procurement-user picker.
 *
 * Replaces the previous shadcn ``<Select>`` implementation per project-wide
 * standard (CLAUDE.md "UI Standards" — every entity-picker MUST be
 * searchable; plain ``<Select>`` is forbidden because it shows UUIDs
 * during SSR and offers no filter). Migrated 2026-05-01 alongside МОЗ Тест
 * fail items #76, #78 — the same Combobox pattern audit produced
 * docs/plans/2026-05-01-searchable-select-audit.md.
 *
 * The public API (``value`` / ``onValueChange`` / ``orgId`` / ``placeholder`` /
 * ``disabled``) matches the previous ``<Select>``-based wrapper so all 6+
 * call sites in admin-routing tabs and dialogs get the upgrade for free.
 *
 * Pattern matches ``features/customers/ui/tab-assignees.tsx`` (the canonical
 * searchable picker in this codebase) — Input + filtered list + click-outside
 * to close + "Не найдено" empty state. No shadcn Combobox / Command import,
 * intentionally kept dependency-free.
 */

interface Props {
  value: string;
  onValueChange: (value: string) => void;
  orgId: string;
  placeholder?: string;
  disabled?: boolean;
}

export function UserSelect({
  value,
  onValueChange,
  orgId,
  placeholder = "Выберите менеджера",
  disabled = false,
}: Props) {
  const [users, setUsers] = useState<ProcurementUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await fetchProcurementUsers(orgId);
        if (!cancelled) setUsers(result);
      } catch (err) {
        console.error("Failed to fetch procurement users:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  // When the controlled `value` changes from outside (e.g., parent resets the
  // form, or a different row is mounted), reflect the selected user's name in
  // the input. Empty string clears the search.
  useEffect(() => {
    if (!value) {
      setSearch("");
      return;
    }
    const u = users.find((x) => x.id === value);
    if (u) setSearch(u.full_name ?? u.id);
  }, [value, users]);

  // Click outside closes the dropdown without committing.
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filtered = users.filter((u) =>
    (u.full_name ?? u.id).toLowerCase().includes(search.toLowerCase())
  );

  function handleSelect(user: ProcurementUser) {
    onValueChange(user.id);
    setSearch(user.full_name ?? user.id);
    setOpen(false);
  }

  return (
    <div className="relative w-full" ref={wrapperRef}>
      <Search
        size={14}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle pointer-events-none"
      />
      <Input
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setOpen(true);
          // Typing past the selected name clears the selection so the parent
          // sees an empty value until the user picks again.
          if (value && e.target.value !== users.find((u) => u.id === value)?.full_name) {
            onValueChange("");
          }
        }}
        onFocus={() => setOpen(true)}
        placeholder={loading ? "Загрузка..." : placeholder}
        disabled={disabled || loading}
        className="h-9 text-sm pl-9"
      />
      {open && !loading && filtered.length > 0 && (
        <div className="absolute z-50 top-full mt-1 w-full bg-white border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
          {filtered.map((user) => (
            <button
              key={user.id}
              type="button"
              onClick={() => handleSelect(user)}
              className="w-full text-left px-3 py-2 text-sm hover:bg-sidebar transition-colors"
            >
              {user.full_name ?? user.id}
            </button>
          ))}
        </div>
      )}
      {open && !loading && search && filtered.length === 0 && (
        <div className="absolute z-50 top-full mt-1 w-full bg-white border border-border rounded-md shadow-lg px-3 py-2 text-sm text-text-muted">
          Не найдено
        </div>
      )}
    </div>
  );
}
