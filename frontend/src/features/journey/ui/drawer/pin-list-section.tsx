"use client";

/**
 * Pin-list section — QA pins with latest verification (Req 5.1).
 *
 * Hidden by the parent for ghost nodes. Verify buttons in Req 5.1 land in
 * a later task (Task 22 — verification flow); here we display the latest
 * verification result inline, read-only.
 *
 * Task 21 adds the "+ Добавить пин" button + `PinCreator` dialog. Button is
 * visible only to users holding pin-writer roles (Req 8.1) — gated via
 * `canCreatePin(userRoles)`.
 */

import { useState } from "react";

import {
  canCreatePin,
  type JourneyNodeDetail,
  type JourneyPin,
  type RoleSlug,
  type VerifyResult,
} from "@/entities/journey";
import { Button } from "@/components/ui/button";
import {
  PinCreator,
  classifyPinBadgeState,
} from "@/features/journey/ui/pin-overlay";

const RESULT_LABELS: Record<VerifyResult, string> = {
  verified: "Проверено",
  broken: "Сломано",
  skip: "Пропущено",
};

const RESULT_CLASS: Record<VerifyResult, string> = {
  verified: "bg-success-subtle text-success",
  broken: "bg-destructive/10 text-destructive",
  skip: "bg-background text-text-muted",
};

export interface PinListSectionProps {
  readonly detail: JourneyNodeDetail;
  /**
   * Current user's held role slugs. Task 21 uses this to gate the
   * "+ Добавить пин" button behind `canCreatePin`. Empty / omitted →
   * read-only list, no create affordance.
   */
  readonly userRoles?: readonly RoleSlug[];
  /** User ID for the `created_by` column — omit → button hidden. */
  readonly userId?: string;
}

function qaPins(pins: readonly JourneyPin[]): JourneyPin[] {
  return pins.filter((p) => p.mode === "qa");
}

export function PinListSection({
  detail,
  userRoles = [],
  userId,
}: PinListSectionProps) {
  const pins = qaPins(detail.pins);
  const [creatorOpen, setCreatorOpen] = useState(false);
  const canCreate = Boolean(userId) && canCreatePin(userRoles);

  return (
    <section
      data-testid="pin-list-section"
      className="p-4"
      aria-label="QA-пины"
    >
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
          QA-пины ({pins.length})
        </h3>
        {canCreate && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => setCreatorOpen(true)}
            data-testid="pin-create-open"
          >
            + Добавить пин
          </Button>
        )}
      </div>
      {pins.length === 0 ? (
        <p className="text-xs text-text-subtle">QA-пины ещё не созданы</p>
      ) : (
        <ul className="space-y-2">
          {pins.map((pin) => {
            const latest = detail.verifications_by_pin[pin.id];
            const badge = classifyPinBadgeState(pin);
            return (
              <li
                key={pin.id}
                data-testid={`pin-list-item-${pin.id}`}
                data-state={badge}
                className="rounded-md border border-border-light bg-background p-2 text-xs"
              >
                <p className="font-medium text-text">{pin.expected_behavior}</p>
                <p className="mt-1 break-all font-mono text-text-subtle">
                  {pin.selector}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1">
                  {latest && (
                    <span
                      className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium ${RESULT_CLASS[latest.result]}`}
                    >
                      {RESULT_LABELS[latest.result]}
                    </span>
                  )}
                  {badge === "broken" && (
                    <span className="inline-flex items-center rounded-md bg-destructive/10 px-1.5 py-0.5 text-[11px] font-medium text-destructive">
                      Селектор сломан
                    </span>
                  )}
                  {badge === "pending" && (
                    <span className="inline-flex items-center rounded-md bg-background px-1.5 py-0.5 text-[11px] font-medium text-text-subtle">
                      Позиция не обновлена
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {canCreate && userId && (
        <PinCreator
          open={creatorOpen}
          onOpenChange={setCreatorOpen}
          nodeId={detail.node_id}
          nodeRoute={detail.route}
          userId={userId}
        />
      )}
    </section>
  );
}
