"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { returnQuoteForRevision } from "@/entities/quote/mutations";

interface ReturnSheetDialogProps {
  quoteId: string;
  userId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function ReturnSheetDialog({
  quoteId,
  userId,
  open,
  onOpenChange,
  onSuccess,
}: ReturnSheetDialogProps) {
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  async function handleSubmit() {
    if (comment.trim().length < 5) {
      setValidationError("Комментарий должен содержать минимум 5 символов");
      return;
    }

    setValidationError(null);
    setLoading(true);
    try {
      await returnQuoteForRevision(quoteId, userId, comment.trim());
      toast.success("КП возвращено на доработку");
      setComment("");
      onOpenChange(false);
      onSuccess();
    } catch {
      toast.error("Не удалось вернуть КП на доработку");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Вернуть на доработку</SheetTitle>
          <SheetDescription>Укажите причину возврата КП</SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-4 px-4">
          <div className="flex flex-col gap-1.5">
            <Textarea
              value={comment}
              onChange={(e) => {
                setComment(e.target.value);
                if (validationError) setValidationError(null);
              }}
              placeholder="Опишите что нужно исправить..."
              rows={4}
              className={validationError ? "border-destructive" : ""}
            />
            {validationError && (
              <p className="text-xs text-destructive">{validationError}</p>
            )}
          </div>

          <Button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full"
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            Отправить на доработку
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
