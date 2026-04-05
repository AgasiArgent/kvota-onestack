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
import { parseVideoUrl } from "@/entities/training-video/types";
import { createTrainingVideo } from "@/entities/training-video/mutations";

interface CreateVideoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
  userId: string;
  existingCategories: string[];
}

export function CreateVideoDialog({
  open,
  onOpenChange,
  orgId,
  userId,
  existingCategories,
}: CreateVideoDialogProps) {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [platformHint, setPlatformHint] = useState("");

  // Reset form on open
  useEffect(() => {
    if (open) {
      setUrl("");
      setTitle("");
      setCategory("");
      setDescription("");
      setPlatformHint("");
    }
  }, [open]);

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
      await createTrainingVideo({
        orgId,
        userId,
        title,
        url,
        category: category || "Общее",
        description,
      });
      toast.success("Видео добавлено");
      onOpenChange(false);
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка при создании видео";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Добавить видео</DialogTitle>
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
              placeholder="https://rutube.ru/video/... или https://youtube.com/watch?v=..."
              autoFocus
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
              list="category-options"
            />
            {existingCategories.length > 0 && (
              <datalist id="category-options">
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
              onClick={() => onOpenChange(false)}
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
              Добавить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
