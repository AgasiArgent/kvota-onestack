"use client";

/**
 * VisibilitySelector — per-material access controls for the training editor
 * (Testing 2 row 54).
 *
 * Renders two SEARCHABLE multi-selects (project rule: all selects searchable):
 *   - Отделы (departments)  → department slugs from DEPARTMENT_SLUGS
 *   - Должности (roles)     → role slugs from kvota.roles (passed in)
 *
 * Leaving both empty means the material is visible to everyone. The component
 * is fully controlled — the parent owns both arrays and is notified via the
 * onChange callbacks. We never mutate the incoming arrays.
 */

import { MultiSelectFilter } from "@/shared/ui/filter-bar";
import { DEPARTMENT_SLUGS, DEPARTMENT_LABELS_RU } from "@/shared/lib/roles";

export interface VisibilityRoleOption {
  slug: string;
  name: string;
}

interface VisibilitySelectorProps {
  /** Available role options (slug + Russian name) from the organization. */
  roleOptions: VisibilityRoleOption[];
  /** Currently selected department slugs (controlled). */
  selectedDepartments: string[];
  /** Currently selected role slugs (controlled). */
  selectedRoles: string[];
  onDepartmentsChange: (next: string[]) => void;
  onRolesChange: (next: string[]) => void;
}

const DEPARTMENT_OPTIONS = DEPARTMENT_SLUGS.map((slug) => ({
  value: slug,
  label: DEPARTMENT_LABELS_RU[slug],
}));

export function VisibilitySelector({
  roleOptions,
  selectedDepartments,
  selectedRoles,
  onDepartmentsChange,
  onRolesChange,
}: VisibilitySelectorProps) {
  const roleSelectOptions = roleOptions.map((r) => ({
    value: r.slug,
    label: r.name,
  }));

  const isRestricted =
    selectedDepartments.length > 0 || selectedRoles.length > 0;

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Доступ
      </span>
      <div className="flex flex-wrap gap-2">
        <MultiSelectFilter
          label="Отделы"
          options={DEPARTMENT_OPTIONS}
          selected={selectedDepartments}
          onChange={(values) => onDepartmentsChange([...values])}
          searchPlaceholder="Поиск отдела..."
          emptyMessage="Нет отделов"
        />
        <MultiSelectFilter
          label="Должности"
          options={roleSelectOptions}
          selected={selectedRoles}
          onChange={(values) => onRolesChange([...values])}
          searchPlaceholder="Поиск должности..."
          emptyMessage="Нет должностей"
        />
      </div>
      <span className="text-xs text-muted-foreground">
        {isRestricted
          ? "Материал виден только выбранным отделам и должностям"
          : "Материал виден всем сотрудникам"}
      </span>
    </div>
  );
}
