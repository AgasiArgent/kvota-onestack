"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ArrowLeft, ExternalLink, ChevronDown } from "lucide-react";
import type { FeedbackDetail as FeedbackDetailType } from "@/entities/admin/types";
import {
  FEEDBACK_TYPE_LABELS,
  FEEDBACK_TYPE_COLORS,
  FEEDBACK_STATUS_LABELS,
  FEEDBACK_STATUS_COLORS,
} from "@/entities/admin/types";
import { updateFeedbackStatus } from "@/entities/admin/mutations";

interface FeedbackDetailProps {
  feedback: FeedbackDetailType;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const STATUS_OPTIONS = ["new", "in_progress", "resolved", "closed"] as const;

export function FeedbackDetailView({ feedback }: FeedbackDetailProps) {
  const router = useRouter();
  const [status, setStatus] = useState(feedback.status);
  const [statusLabel, setStatusLabel] = useState(
    FEEDBACK_STATUS_LABELS[feedback.status] ?? feedback.status
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const typeColor =
    FEEDBACK_TYPE_COLORS[feedback.feedback_type] ?? "bg-slate-100 text-slate-700";
  const statusColor =
    FEEDBACK_STATUS_COLORS[feedback.status] ?? "bg-slate-100 text-slate-700";

  async function handleStatusSave() {
    if (status === feedback.status) return;
    setSaving(true);
    setError(null);

    try {
      await updateFeedbackStatus(feedback.short_id, status);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Ошибка при обновлении статуса"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Back link */}
      <Link
        href="/admin/feedback"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft size={16} />
        Назад к обращениям
      </Link>

      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${typeColor}`}
        >
          {FEEDBACK_TYPE_LABELS[feedback.feedback_type] ?? feedback.feedback_type}
        </span>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${statusColor}`}
        >
          {FEEDBACK_STATUS_LABELS[feedback.status] ?? feedback.status}
        </span>
        <span className="font-mono text-sm text-muted-foreground">
          {feedback.short_id}
        </span>
      </div>

      {/* Info section */}
      <Card className="p-4 space-y-2">
        <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <span className="text-muted-foreground">Отправитель:</span>
          <span>
            {feedback.user_name ?? "\u2014"}
            {feedback.user_email && (
              <span className="text-muted-foreground ml-1">
                ({feedback.user_email})
              </span>
            )}
          </span>

          {feedback.page_url && (
            <>
              <span className="text-muted-foreground">Страница:</span>
              <a
                href={feedback.page_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline truncate"
              >
                {feedback.page_url}
              </a>
            </>
          )}

          <span className="text-muted-foreground">Дата:</span>
          <span>{formatDate(feedback.created_at)}</span>
        </div>
      </Card>

      {/* Description */}
      <div className="border-l-4 border-accent pl-4 py-3 bg-muted/30 rounded-r-lg">
        <p className="text-sm whitespace-pre-wrap">{feedback.description}</p>
      </div>

      {/* Screenshot */}
      {feedback.screenshot_url && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium">Скриншот</h3>
          <button
            type="button"
            onClick={() => setLightboxOpen(true)}
            className="cursor-zoom-in"
          >
            <Image
              src={feedback.screenshot_url}
              alt="Скриншот обращения"
              width={600}
              height={400}
              className="rounded-lg border max-w-full h-auto"
              unoptimized
            />
          </button>

          <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
            <DialogContent className="sm:max-w-4xl p-2" showCloseButton>
              <Image
                src={feedback.screenshot_url}
                alt="Скриншот обращения"
                width={1200}
                height={800}
                className="w-full h-auto rounded"
                unoptimized
              />
            </DialogContent>
          </Dialog>
        </div>
      )}

      {/* Debug context */}
      {feedback.debug_context && Object.keys(feedback.debug_context).length > 0 && (
        <Collapsible>
          <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
            <ChevronDown size={16} />
            Отладочная информация
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2">
            <pre className="bg-muted p-3 rounded-lg text-xs overflow-x-auto">
              {JSON.stringify(feedback.debug_context, null, 2)}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Status update */}
      <Card className="p-4 space-y-3">
        <h3 className="text-sm font-medium">Обновить статус</h3>
        <div className="flex items-center gap-3">
          <Select
            value={status}
            onValueChange={(v) => {
              if (!v) return;
              setStatus(v as typeof status);
              setStatusLabel(FEEDBACK_STATUS_LABELS[v] ?? v);
            }}
          >
            <SelectTrigger className="w-[200px]">
              <span>{statusLabel}</span>
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>
                  {FEEDBACK_STATUS_LABELS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            onClick={handleStatusSave}
            disabled={saving || status === feedback.status}
            size="sm"
          >
            {saving ? "Сохранение..." : "Сохранить"}
          </Button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </Card>

      {/* ClickUp link */}
      {feedback.clickup_task_id && (
        <a
          href={`https://app.clickup.com/t/${feedback.clickup_task_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm text-accent hover:underline"
        >
          <ExternalLink size={14} />
          Открыть в ClickUp
        </a>
      )}
    </div>
  );
}
