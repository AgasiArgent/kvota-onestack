"use client";

import { useMemo } from "react";
import {
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { LogisticsSegment } from "@/entities/logistics-segment";
import { cn } from "@/lib/utils";
import { SegmentNode } from "./segment-node";
import { SegmentEdge } from "./segment-edge";

/**
 * SegmentTimeline — drag&drop list of route segments.
 *
 * Uses @dnd-kit/sortable: click+drag on the grip handle (or any card area)
 * reorders the sequence. Order changes are flushed via {@link onReorder}
 * with the new array; the parent calls the server action for each changed
 * row, then router.refresh() to pull fresh `sequence_order` from DB.
 *
 * Empty-state card nudges the user to pick a template or add a segment —
 * matches the wireframe at docs/superpowers/.../02-route-constructor.html.
 */

interface SegmentTimelineProps {
  segments: LogisticsSegment[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onReorder: (next: LogisticsSegment[]) => void;
  onDelete: (id: string) => void;
  disabled?: boolean;
  className?: string;
}

export function SegmentTimeline({
  segments,
  selectedId,
  onSelect,
  onReorder,
  onDelete,
  disabled,
  className,
}: SegmentTimelineProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const ids = useMemo(() => segments.map((s) => s.id), [segments]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = ids.indexOf(String(active.id));
    const newIndex = ids.indexOf(String(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(segments, oldIndex, newIndex).map((s, i) => ({
      ...s,
      sequenceOrder: i + 1,
    }));
    onReorder(reordered);
  }

  if (segments.length === 0) {
    return (
      <div
        className={cn(
          "rounded-lg border border-dashed border-border-light bg-card px-6 py-10 text-center",
          className,
        )}
      >
        <p className="text-sm text-text-muted">
          Маршрут пока пуст. Примените шаблон или добавьте сегмент.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-border-light bg-card",
        className,
      )}
    >
      <header className="flex items-center justify-between border-b border-border-light px-4 py-3">
        <h3 className="text-sm font-semibold text-text">
          Маршрут · {segments.length}{" "}
          {segments.length === 1 ? "сегмент" : "сегментов"}
        </h3>
        <span className="text-xs text-text-subtle">
          Перетаскивайте карточки, чтобы изменить порядок
        </span>
      </header>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          <ol className="flex flex-col gap-2 p-3">
            {segments.map((segment) => (
              <SortableSegmentRow
                key={segment.id}
                segment={segment}
                selected={selectedId === segment.id}
                onSelect={onSelect}
                onDelete={onDelete}
                disabled={disabled}
              />
            ))}
          </ol>
        </SortableContext>
      </DndContext>
    </div>
  );
}

interface SortableSegmentRowProps {
  segment: LogisticsSegment;
  selected: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  disabled?: boolean;
}

function SortableSegmentRow({
  segment,
  selected,
  onSelect,
  onDelete,
  disabled,
}: SortableSegmentRowProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: segment.id, disabled });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        "relative",
        isDragging && "z-10 opacity-60",
      )}
    >
      <div
        role="button"
        tabIndex={0}
        aria-selected={selected}
        onClick={() => onSelect(segment.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(segment.id);
          }
        }}
        className={cn(
          "grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-md border bg-card p-3",
          "cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          selected
            ? "border-accent bg-accent-subtle/60"
            : "border-border-light hover:border-border",
        )}
      >
        <button
          type="button"
          {...attributes}
          {...listeners}
          aria-label="Перетащить"
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-sm text-text-muted",
            "cursor-grab active:cursor-grabbing hover:bg-sidebar hover:text-text",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
            disabled && "cursor-not-allowed opacity-40",
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <GripVertical size={14} strokeWidth={2} aria-hidden />
        </button>

        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex size-6 items-center justify-center rounded-sm bg-sidebar text-xs font-semibold text-text",
              )}
              aria-hidden
            >
              {segment.sequenceOrder}
            </span>
            <SegmentNode location={segment.fromLocation} placeholder="Откуда" />
            <SegmentNode location={segment.toLocation} placeholder="Куда" />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
            {segment.label && <span className="truncate">{segment.label}</span>}
            {segment.carrier && (
              <>
                <span className="text-text-subtle">·</span>
                <span className="truncate">{segment.carrier}</span>
              </>
            )}
            <SegmentEdge segment={segment} className="ml-auto" />
          </div>
        </div>

        <div className="flex items-center">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Удалить сегмент"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(segment.id);
            }}
            disabled={disabled}
            className="text-text-muted hover:text-error"
          >
            <Trash2 size={14} strokeWidth={2} />
          </Button>
        </div>
      </div>
    </li>
  );
}
