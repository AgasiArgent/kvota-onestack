"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Pencil, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  createLogisticsTemplate,
  updateLogisticsTemplate,
  deleteLogisticsTemplate,
} from "@/entities/logistics-template";
import type { LocationType } from "@/entities/location/ui/location-chip";
import type { LogisticsTemplateAdmin } from "../model/types";
import { LogisticsTemplateDialog } from "./logistics-template-dialog";

/**
 * LogisticsTemplatesTab — admin CRUD over logistics_route_templates.
 *
 * A template is a reusable scaffold for routes — stored as an ordered
 * sequence of (from_type, to_type) pairs. Logisticians pick a template
 * from the Route Constructor to pre-populate segment shapes (actual
 * locations are chosen per-invoice).
 *
 * Wave 2 Task 15: list + create + edit + delete.
 */

interface Props {
  templates: LogisticsTemplateAdmin[];
  orgId: string;
}

const TYPE_LABELS: Record<LocationType, string> = {
  supplier: "Поставщик",
  hub: "Хаб",
  customs: "Таможня",
  own_warehouse: "Склад",
  client: "Клиент",
};

function formatTypeChain(
  segments: LogisticsTemplateAdmin["segments"],
): string {
  if (segments.length === 0) return "—";
  const stops: string[] = [
    TYPE_LABELS[segments[0].from_location_type as LocationType] ??
      segments[0].from_location_type,
  ];
  for (const s of segments) {
    stops.push(
      TYPE_LABELS[s.to_location_type as LocationType] ?? s.to_location_type,
    );
  }
  return stops.join(" → ");
}

type TemplateSegmentForm = {
  sequence_order: number;
  from_location_type: LocationType;
  to_location_type: LocationType;
  default_label: string;
  default_days: number | null;
};

function toDialogInitial(t: LogisticsTemplateAdmin): {
  name: string;
  description: string;
  segments: TemplateSegmentForm[];
} {
  return {
    name: t.name,
    description: t.description ?? "",
    segments: t.segments.map((s, i) => ({
      sequence_order: i + 1,
      from_location_type: s.from_location_type as LocationType,
      to_location_type: s.to_location_type as LocationType,
      default_label: s.default_label ?? "",
      default_days: s.default_days,
    })),
  };
}

export function LogisticsTemplatesTab({ templates }: Props) {
  const router = useRouter();
  const [dialogMode, setDialogMode] = useState<
    | { kind: "closed" }
    | { kind: "create" }
    | { kind: "edit"; template: LogisticsTemplateAdmin }
  >({ kind: "closed" });
  const [isPending, startTransition] = useTransition();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleSubmit = async (input: {
    name: string;
    description: string;
    segments: TemplateSegmentForm[];
  }) => {
    startTransition(async () => {
      try {
        const payload = {
          name: input.name,
          description: input.description || undefined,
          segments: input.segments.map((s) => ({
            sequence_order: s.sequence_order,
            from_location_type: s.from_location_type,
            to_location_type: s.to_location_type,
            default_label: s.default_label || undefined,
            default_days: s.default_days ?? undefined,
          })),
          revalidate_path: "/admin/routing?tab=logistics",
        };
        if (dialogMode.kind === "edit") {
          await updateLogisticsTemplate({
            template_id: dialogMode.template.id,
            ...payload,
          });
          toast.success("Шаблон обновлён");
        } else {
          await createLogisticsTemplate(payload);
          toast.success("Шаблон создан");
        }
        setDialogMode({ kind: "closed" });
        router.refresh();
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось сохранить шаблон",
        );
      }
    });
  };

  const handleDelete = (id: string, name: string) => {
    if (!confirm(`Удалить шаблон «${name}»? Это действие необратимо.`)) return;
    setDeletingId(id);
    startTransition(async () => {
      try {
        await deleteLogisticsTemplate({
          template_id: id,
          revalidate_path: "/admin/routing?tab=logistics",
        });
        toast.success("Шаблон удалён");
        router.refresh();
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось удалить",
        );
      } finally {
        setDeletingId(null);
      }
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text">
            Шаблоны маршрутов логистики
          </h2>
          <p className="text-sm text-text-muted">
            Переиспользуемые скелеты маршрутов — типовые цепочки
            поставщик → хаб → таможня → клиент. Логисты применяют шаблон в
            Конструкторе маршрута на этапе Логистики КП.
          </p>
        </div>
        <Button
          onClick={() => setDialogMode({ kind: "create" })}
          disabled={isPending}
          className="shrink-0"
        >
          <Plus size={16} className="mr-1" aria-hidden /> Новый шаблон
        </Button>
      </div>

      {templates.length === 0 ? (
        <div className="rounded-lg border border-border-light bg-card p-8 text-center">
          <p className="text-sm text-text-muted">
            Пока нет ни одного шаблона. Создайте первый — логисты смогут
            выбирать его в конструкторе маршрутов.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-border-light bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-sidebar text-xs uppercase tracking-wide text-text-muted">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Название</th>
                <th className="px-4 py-2 text-left font-medium">Маршрут</th>
                <th className="px-4 py-2 text-left font-medium">Сегментов</th>
                <th className="px-4 py-2 text-left font-medium">Автор</th>
                <th className="px-4 py-2 text-right font-medium">Действия</th>
              </tr>
            </thead>
            <tbody>
              {templates.map((t) => (
                <tr
                  key={t.id}
                  className="border-t border-border-light hover:bg-sidebar/40"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-text">{t.name}</div>
                    {t.description && (
                      <div className="text-xs text-text-muted">
                        {t.description}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    <span className="inline-flex items-center gap-1">
                      {formatTypeChain(t.segments)}
                    </span>
                  </td>
                  <td className="px-4 py-3 tabular-nums text-text-muted">
                    {t.segments.length}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {t.created_by_name ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setDialogMode({ kind: "edit", template: t })
                        }
                        disabled={isPending}
                        aria-label={`Редактировать шаблон ${t.name}`}
                      >
                        <Pencil
                          size={14}
                          className="text-text-muted"
                          aria-hidden
                        />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(t.id, t.name)}
                        disabled={isPending}
                        aria-label={`Удалить шаблон ${t.name}`}
                      >
                        {deletingId === t.id ? (
                          <Loader2
                            size={14}
                            className="animate-spin text-text-muted"
                            aria-hidden
                          />
                        ) : (
                          <Trash2
                            size={14}
                            className="text-text-muted"
                            aria-hidden
                          />
                        )}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <LogisticsTemplateDialog
        open={dialogMode.kind !== "closed"}
        onOpenChange={(o) => {
          if (!o) setDialogMode({ kind: "closed" });
        }}
        onSubmit={handleSubmit}
        busy={isPending}
        initial={
          dialogMode.kind === "edit"
            ? toDialogInitial(dialogMode.template)
            : undefined
        }
      />
    </div>
  );
}
