"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import type { TrainingVideo } from "@/entities/training-video/types";
import { parseVideoUrl } from "@/entities/training-video/types";
import { updateTrainingVideo } from "@/entities/training-video/mutations";

interface EditVideoDialogProps {
  video: TrainingVideo | null;
  onClose: () => void;
  existingCategories: string[];
  orgId: string;
}

/**
 * Reconstruct a display URL from stored video_id + platform.
 */
function reconstructUrl(videoId: string, platform: string): string {
  if (platform === "youtube") {
    return `https://youtube.com/watch?v=${videoId}`;
  }
  // RuTube: videoId may contain ?p=TOKEN for private videos
  if (videoId.includes("?p=")) {
    const [hash, rest] = videoId.split("?");
    return `https://rutube.ru/video/private/${hash}/?${rest}`;
  }
  return `https://rutube.ru/video/${videoId}/`;
}

export function EditVideoDialog({
  video,
  onClose,
  existingCategories,
  orgId,
}: EditVideoDialogProps) {
  const router = useRouter();
  const isOpen = video !== null;

  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [platformHint, setPlatformHint] = useState("");

  // Populate form when video changes
  useEffect(() => {
    if (video) {
      setUrl(reconstructUrl(video.youtube_id, video.platform));
      setTitle(video.title);
      setCategory(video.category);
      setDescription(video.description ?? "");
      setPlatformHint(video.platform === "rutube" ? "RuTube" : "YouTube");
    }
  }, [video]);

  function handleUrlChange(value: string) {
    setUrl(value);
    const parsed = parseVideoUrl(value);
    if (parsed) {
      setPlatformHint(parsed.platform === "rutube" ? "RuTube" : "YouTube");
    } else {
      setPlatformHint(value.length > 10 ? "Ссылка не распознана" : "");
    }
  }

  async function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!video) return;

    if (!url.trim()) {
      toast.error("Укажите ссылку на видео");
      return;
    }

    if (!title.trim()) {
      toast.error("Укажите название видео");
      return;
    }

    const parsed = parseVideoUrl(url);
    if (!parsed) {
      toast.error("Не удалось распознать ссылку на видео");
      return;
    }

    setSubmitting(true);
    try {
      await updateTrainingVideo(video.id, orgId, {
        title,
        url,
        category: category || "Общее",
        description,
      });
      toast.success("Видео обновлено");
      onClose();
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка при обновлении видео";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Редактировать видео</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* URL */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Ссылка на видео <span className="text-destructive">*</span>
            </Label>
            <Input
              value={url}
              onChange={(e) => handleUrlChange(e.target.value)}
              placeholder="https://rutube.ru/video/..."
            />
            {platformHint && (
              <span className="text-xs text-muted-foreground">
                {platformHint}
              </span>
            )}
          </div>

          {/* Title */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Название <span className="text-destructive">*</span>
            </Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Название видео"
            />
          </div>

          {/* Category */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Категория
            </Label>
            <Input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="Общее"
              list="edit-category-options"
            />
            {existingCategories.length > 0 && (
              <datalist id="edit-category-options">
                {existingCategories.map((cat) => (
                  <option key={cat} value={cat} />
                ))}
              </datalist>
            )}
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Описание
            </Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Краткое описание видео"
              rows={3}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={submitting}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={!url.trim() || !title.trim() || submitting}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Сохранить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
