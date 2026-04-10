"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { createClient } from "@/shared/lib/supabase/client";
import { DOCUMENT_TYPE_OPTIONS, DOCUMENT_TYPE_LABELS } from "./constants";

interface PromoteDocumentDialogProps {
  document: {
    id: string;
    original_filename: string;
    document_type: string | null;
    description: string | null;
  } | null;
  onClose: () => void;
  onPromoted: () => void;
}

/**
 * Prompts the user to classify a chat-media document (status=draft, linked
 * to a comment) as an official document (status=final) by picking a
 * document_type and optional description.
 */
export function PromoteDocumentDialog({
  document,
  onClose,
  onPromoted,
}: PromoteDocumentDialogProps) {
  const [documentType, setDocumentType] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [saving, setSaving] = useState(false);

  // Sync form state when the target document changes (e.g. user opens the
  // dialog on a different chat-media file).
  useEffect(() => {
    if (!document) return;
    setDocumentType(document.document_type ?? "");
    setDescription(document.description ?? "");
  }, [document]);

  async function handleSubmit() {
    if (!document) return;
    if (!documentType) {
      toast.error("Укажите тип документа");
      return;
    }

    setSaving(true);
    try {
      const supabase = createClient();
      const { error } = await supabase
        .from("documents")
        .update({
          document_type: documentType,
          description: description || null,
          status: "final",
        })
        .eq("id", document.id);

      if (error) throw new Error(error.message);

      toast.success("Документ отмечен как официальный");
      onPromoted();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ошибка";
      toast.error(`Не удалось сохранить: ${msg}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={document !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Сделать документ официальным</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="text-sm text-muted-foreground truncate">
            {document?.original_filename}
          </div>

          <div className="space-y-2">
            <Label htmlFor="promote-type">
              Тип документа <span className="text-destructive">*</span>
            </Label>
            <Select
              value={documentType}
              onValueChange={(v) => setDocumentType(v ?? "")}
            >
              <SelectTrigger id="promote-type">
                <SelectValue placeholder="Выберите тип">
                  {documentType
                    ? DOCUMENT_TYPE_LABELS[documentType] ?? documentType
                    : undefined}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {DOCUMENT_TYPE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="promote-desc">Описание (необязательно)</Label>
            <Input
              id="promote-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Краткое описание"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Отмена
          </Button>
          <Button onClick={handleSubmit} disabled={saving || !documentType}>
            {saving ? "Сохранение…" : "Сделать официальным"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
