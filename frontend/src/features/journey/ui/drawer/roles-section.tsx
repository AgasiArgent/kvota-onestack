"use client";

/**
 * Roles section — simple badge list (Req 5.1).
 */

import type { JourneyNodeDetail } from "@/entities/journey";

export interface RolesSectionProps {
  readonly detail: JourneyNodeDetail;
}

export function RolesSection({ detail }: RolesSectionProps) {
  return (
    <section
      data-testid="roles-section"
      className="p-4"
      aria-label="Роли"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Роли
      </h3>
      {detail.roles.length === 0 ? (
        <p className="text-xs text-text-subtle">Роли не заданы</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {detail.roles.map((role) => (
            <li
              key={role}
              className="inline-flex items-center rounded-md bg-accent-subtle px-2 py-0.5 text-xs font-medium text-accent"
            >
              {role}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
