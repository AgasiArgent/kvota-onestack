"use client";

import { useState, useEffect } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchProcurementUsers } from "../api/routing-api";
import type { ProcurementUser } from "../model/types";

interface Props {
  value: string;
  onValueChange: (value: string) => void;
  orgId: string;
  placeholder?: string;
  disabled?: boolean;
}

// Base UI Select's onValueChange passes (string | null), wrap for consumers
type SelectChangeHandler = (value: string | null) => void;

export function UserSelect({
  value,
  onValueChange,
  orgId,
  placeholder = "Выберите менеджера",
  disabled = false,
}: Props) {
  const [users, setUsers] = useState<ProcurementUser[]>([]);
  const [loading, setLoading] = useState(true);

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

  return (
    <Select value={value} onValueChange={((val: string | null) => onValueChange(val ?? "")) as SelectChangeHandler} disabled={disabled || loading}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder={loading ? "Загрузка..." : placeholder} />
      </SelectTrigger>
      <SelectContent>
        {users.map((user) => (
          <SelectItem key={user.id} value={user.id}>
            {user.full_name ?? user.id}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
