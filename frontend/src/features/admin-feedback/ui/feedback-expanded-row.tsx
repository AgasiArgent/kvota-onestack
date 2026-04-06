"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ExternalLink, ChevronDown } from "lucide-react";
import type { FeedbackDetail } from "@/entities/admin/types";
import { fetchFeedbackDetailClient } from "@/entities/admin/mutations";

interface FeedbackExpandedRowProps {
  shortId: string;
}

function ExpandedSkeleton() {
  return (
    <div className="p-4 space-y-3 animate-pulse">
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
        <div className="h-4 w-24 bg-muted rounded" />
        <div className="h-4 w-48 bg-muted rounded" />
        <div className="h-4 w-20 bg-muted rounded" />
        <div className="h-4 w-64 bg-muted rounded" />
      </div>
      <div className="h-20 bg-muted rounded" />
    </div>
  );
}

export function FeedbackExpandedRow({ shortId }: FeedbackExpandedRowProps) {
  const [detail, setDetail] = useState<FeedbackDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(false);
      try {
        const data = await fetchFeedbackDetailClient(shortId);
        if (!cancelled) {
          setDetail(data);
        }
      } catch (err) {
        console.error("Failed to fetch feedback detail:", err);
        if (!cancelled) {
          setError(true);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [shortId]);

  if (loading) {
    return <ExpandedSkeleton />;
  }

  if (error || !detail) {
    return (
      <div className="p-4 flex items-center gap-3 text-sm text-muted-foreground">
        <span>Не удалось загрузить детали обращения</span>
        <button
          type="button"
          className="text-accent hover:underline"
          onClick={(e) => {
            e.stopPropagation();
            setLoading(true);
            setError(false);
            fetchFeedbackDetailClient(shortId)
              .then(setDetail)
              .catch(() => setError(true))
              .finally(() => setLoading(false));
          }}
        >
          Повторить
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4 bg-muted/20 border-t">
      {/* Info grid */}
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <span className="text-muted-foreground">Отправитель:</span>
        <span>
          {detail.user_name ?? "\u2014"}
          {detail.user_email && (
            <span className="text-muted-foreground ml-1">
              ({detail.user_email})
            </span>
          )}
        </span>

        {detail.page_url && (
          <>
            <span className="text-muted-foreground">Страница:</span>
            <a
              href={detail.page_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline truncate"
              onClick={(e) => e.stopPropagation()}
            >
              {detail.page_url}
            </a>
          </>
        )}
      </div>

      {/* Full description */}
      <div className="border-l-4 border-accent pl-4 py-3 bg-muted/30 rounded-r-lg">
        <p className="text-sm whitespace-pre-wrap">{detail.description}</p>
      </div>

      {/* Screenshot with lightbox */}
      {detail.screenshot_url && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Скриншот</h4>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setLightboxOpen(true);
            }}
            className="cursor-zoom-in"
          >
            <Image
              src={detail.screenshot_url}
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
                src={detail.screenshot_url}
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

      {/* Debug context (collapsible) */}
      {detail.debug_context &&
        Object.keys(detail.debug_context).length > 0 && (
          <Collapsible>
            <CollapsibleTrigger
              className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground"
              onClick={(e) => e.stopPropagation()}
            >
              <ChevronDown size={16} />
              Отладочная информация
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-2">
              <pre className="bg-muted p-3 rounded-lg text-xs overflow-x-auto">
                {JSON.stringify(detail.debug_context, null, 2)}
              </pre>
            </CollapsibleContent>
          </Collapsible>
        )}

      {/* ClickUp link */}
      {detail.clickup_task_id && (
        <a
          href={`https://app.clickup.com/t/${detail.clickup_task_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm text-accent hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          <ExternalLink size={14} />
          Открыть в ClickUp
        </a>
      )}
    </div>
  );
}
