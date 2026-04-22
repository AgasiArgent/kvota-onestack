"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import type { LocationOption } from "@/entities/location";
import type {
  LogisticsSegment,
} from "@/entities/logistics-segment";
import {
  createSegment,
  deleteSegment,
  reorderSegment,
} from "@/entities/logistics-segment";
import type { LogisticsTemplate } from "@/entities/logistics-template";
import { applyLogisticsTemplate } from "@/entities/logistics-template";
import { NewSegmentButton } from "./new-segment-button";
import { RouteTotalsCard } from "./route-totals-card";
import { SegmentDetailsPanel } from "./segment-details-panel";
import { SegmentTimeline } from "./segment-timeline";
import { TemplatePicker } from "./template-picker";

/**
 * RouteConstructor — per-invoice timeline UI for the Logistics step.
 *
 * Data flow:
 *   - initialSegments / locations / templates come from a server
 *     component (see frontend/src/features/quotes/ui/logistics-step/).
 *   - Mutations go through @/entities/logistics-segment server actions
 *     (POST/PATCH/DELETE the Python API, then revalidatePath on the
 *     parent quote).
 *   - router.refresh() pulls fresh segments after each write.
 *
 * Client-side `local` mirror enables optimistic UI on field edits so the
 * timeline updates immediately; the server revalidation reconciles any
 * drift on the next refresh cycle.
 */

interface RouteConstructorProps {
  invoiceId: string;
  orgId: string;
  initialSegments: LogisticsSegment[];
  locations: LocationOption[];
  templates: LogisticsTemplate[];
  revalidatePath: string;
  disabled?: boolean;
}

export function RouteConstructor({
  invoiceId,
  initialSegments,
  locations,
  templates,
  revalidatePath,
  disabled,
}: RouteConstructorProps) {
  const router = useRouter();
  const [segments, setSegments] = useState<LogisticsSegment[]>(initialSegments);
  const [selectedId, setSelectedId] = useState<string | null>(
    initialSegments[0]?.id ?? null,
  );
  const [isPending, startTransition] = useTransition();

  // Re-sync when server props change (e.g. after refresh)
  useEffect(() => {
    setSegments(initialSegments);
    setSelectedId((prev) => {
      if (prev && initialSegments.some((s) => s.id === prev)) return prev;
      return initialSegments[0]?.id ?? null;
    });
  }, [initialSegments]);

  const selected = useMemo(
    () => segments.find((s) => s.id === selectedId) ?? null,
    [segments, selectedId],
  );

  function handleLocalUpdate(id: string, patch: Partial<LogisticsSegment>) {
    setSegments((prev) =>
      prev.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    );
  }

  function handleAdd() {
    startTransition(async () => {
      try {
        const res = await createSegment({
          invoice_id: invoiceId,
          sequence_order: segments.length + 1,
          label: "Новый сегмент",
          revalidate_path: revalidatePath,
        });
        if (res?.segment_id) {
          setSelectedId(res.segment_id);
        }
        router.refresh();
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось добавить сегмент",
        );
      }
    });
  }

  function handleDelete(id: string) {
    // Optimistic removal
    const before = segments;
    const next = segments
      .filter((s) => s.id !== id)
      .map((s, i) => ({ ...s, sequenceOrder: i + 1 }));
    setSegments(next);
    if (selectedId === id) {
      setSelectedId(next[0]?.id ?? null);
    }
    startTransition(async () => {
      try {
        await deleteSegment({ segment_id: id, revalidate_path: revalidatePath });
        router.refresh();
      } catch (err) {
        // Rollback
        setSegments(before);
        toast.error(
          err instanceof Error ? err.message : "Не удалось удалить сегмент",
        );
      }
    });
  }

  function handleReorder(next: LogisticsSegment[]) {
    const before = segments;
    setSegments(next);
    startTransition(async () => {
      try {
        // Sequential reorders — small lists (<=10), order matters for UX.
        for (const seg of next) {
          const original = before.find((s) => s.id === seg.id);
          if (!original || original.sequenceOrder === seg.sequenceOrder) continue;
          await reorderSegment({
            segment_id: seg.id,
            new_sequence_order: seg.sequenceOrder,
            revalidate_path: revalidatePath,
          });
        }
        router.refresh();
      } catch (err) {
        setSegments(before);
        toast.error(
          err instanceof Error ? err.message : "Не удалось переставить сегмент",
        );
      }
    });
  }

  function handleApplyTemplate(template: LogisticsTemplate) {
    startTransition(async () => {
      try {
        await applyLogisticsTemplate({
          template_id: template.id,
          invoice_id: invoiceId,
          revalidate_path: revalidatePath,
        });
        toast.success(`Шаблон «${template.name}» применён`);
        router.refresh();
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось применить шаблон",
        );
      }
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col">
          <h2 className="text-lg font-semibold text-text">
            Конструктор маршрута
          </h2>
          <p className="text-xs text-text-muted">
            Соберите маршрут из сегментов — поставщик, хабы, таможня, склад, клиент.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <TemplatePicker
            templates={templates}
            onApply={handleApplyTemplate}
            disabled={disabled || isPending}
          />
          <NewSegmentButton onClick={handleAdd} disabled={disabled || isPending} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_420px]">
        <div className="flex flex-col gap-4 min-w-0">
          <SegmentTimeline
            segments={segments}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onReorder={handleReorder}
            onDelete={handleDelete}
            disabled={disabled || isPending}
          />
          <RouteTotalsCard segments={segments} />
        </div>
        <SegmentDetailsPanel
          segment={selected}
          locations={locations}
          revalidatePath={revalidatePath}
          onLocalUpdate={handleLocalUpdate}
          disabled={disabled || isPending}
        />
      </div>
    </div>
  );
}
