"use client";

/**
 * "View as role" dropdown (Req 3.4).
 *
 * Two states:
 *   - null = "Все роли (admin view)" — no filtering
 *   - RoleSlug = canvas shows only nodes with that role
 *
 * The 13 active roles come from `SessionUser.ACTIVE_ROLES`; labels from
 * `ROLE_LABELS_RU` in the `user` entity. Sidebar is pure UI — parent owns
 * the state.
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { ACTIVE_ROLES, ROLE_LABELS_RU } from "@/entities/user";
import type { RoleSlug } from "@/entities/journey";

const ALL_ROLES_SENTINEL = "__all__";

interface Props {
  readonly value: RoleSlug | null;
  readonly onChange: (next: RoleSlug | null) => void;
}

export function ViewAsRole({ value, onChange }: Props) {
  const current = value ?? ALL_ROLES_SENTINEL;

  const handleChange = (next: string | null) => {
    if (next === null || next === ALL_ROLES_SENTINEL) {
      onChange(null);
    } else {
      onChange(next as RoleSlug);
    }
  };

  const label =
    value === null ? "Все роли" : (ROLE_LABELS_RU[value] ?? value);

  return (
    <div className="flex flex-col gap-1" data-testid="journey-viewas">
      <span className="text-xs text-text-subtle">Смотреть как</span>
      <Select value={current} onValueChange={handleChange}>
        <SelectTrigger className="w-full">
          <span className="flex flex-1 text-left text-sm">{label}</span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_ROLES_SENTINEL}>Все роли</SelectItem>
          {ACTIVE_ROLES.map((role) => (
            <SelectItem key={role} value={role}>
              {ROLE_LABELS_RU[role] ?? role}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
