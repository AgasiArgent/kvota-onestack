"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { TrainingVideo } from "@/entities/training-video/types";
import { deleteTrainingVideo } from "@/entities/training-video/mutations";

interface DeleteVideoDialogProps {
  video: TrainingVideo | null;
  onClose: () => void;
}

export function DeleteVideoDialog({ video, onClose }: DeleteVideoDialogProps) {
  const router = useRouter();
  const isOpen = video !== null;
  const [submitting, setSubmitting] = useState(false);

  async function handleDelete() {
    if (!video) return;

    setSubmitting(true);
    try {
      await deleteTrainingVideo(video.id);
      toast.success("Видео удалено");
      onClose();
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка при удалении видео";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Удалить видео</DialogTitle>
          <DialogDescription>
            Вы уверены, что хотите удалить &laquo;{video?.title}&raquo;? Это
            действие нельзя отменить.
          </DialogDescription>
        </DialogHeader>

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
            type="button"
            variant="destructive"
            onClick={handleDelete}
            disabled={submitting}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Удалить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
