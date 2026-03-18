"use client";

import { Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { TrainingVideo } from "@/entities/training-video/types";

interface VideoCardProps {
  video: TrainingVideo;
  embedUrl: string;
  isAdmin: boolean;
  onEdit: () => void;
  onDelete: () => void;
}

export function VideoCard({
  video,
  embedUrl,
  isAdmin,
  onEdit,
  onDelete,
}: VideoCardProps) {
  const iframeAllow =
    video.platform === "rutube"
      ? "clipboard-write; autoplay"
      : "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";

  return (
    <div className="group rounded-lg border border-border bg-background overflow-hidden">
      {/* Video embed */}
      <div className="aspect-video relative">
        <iframe
          src={embedUrl}
          className="absolute inset-0 w-full h-full"
          allow={iframeAllow}
          allowFullScreen
          title={video.title}
        />
      </div>

      {/* Info */}
      <div className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-medium leading-snug">{video.title}</h3>
          {isAdmin && (
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={onEdit}
                title="Редактировать"
              >
                <Pencil size={14} />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={onDelete}
                title="Удалить"
                className="text-destructive hover:text-destructive"
              >
                <Trash2 size={14} />
              </Button>
            </div>
          )}
        </div>

        {video.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {video.description}
          </p>
        )}

        <Badge variant="secondary">{video.category}</Badge>
      </div>
    </div>
  );
}
