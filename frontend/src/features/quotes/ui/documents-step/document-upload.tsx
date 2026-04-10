"use client";

import { useState, useRef } from "react";
import { Upload, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { createClient } from "@/shared/lib/supabase/client";
import { DOCUMENT_TYPE_OPTIONS, DOCUMENT_TYPE_LABELS } from "./constants";

interface DocumentUploadProps {
  quoteId: string;
  orgId: string;
  userId: string;
  onUploaded: () => void;
}

export function DocumentUpload({
  quoteId,
  orgId,
  userId,
  onUploaded,
}: DocumentUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [documentType, setDocumentType] = useState("other");
  const [description, setDescription] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const supabase = createClient();
      const ext = file.name.split(".").pop()?.toLowerCase() || "bin";
      const storagePath = `quotes/${quoteId}/${crypto.randomUUID()}.${ext}`;

      const { error: uploadError } = await supabase.storage
        .from("kvota-documents")
        .upload(storagePath, file);
      if (uploadError) {
        if (uploadError.message?.includes("mime") || uploadError.message?.includes("type")) {
          throw new Error(
            `Формат файла "${ext}" не поддерживается. Допустимые: PDF, Word, Excel, JPG, PNG, WebP, ZIP`
          );
        }
        if (uploadError.message?.includes("size") || uploadError.message?.includes("limit")) {
          const sizeMb = Math.round(file.size / 1024 / 1024);
          throw new Error(`Файл слишком большой (${sizeMb} МБ). Максимум: 50 МБ`);
        }
        throw new Error(`Ошибка загрузки: ${uploadError.message}`);
      }

      const { error: insertError } = await supabase.from("documents").insert({
        organization_id: orgId,
        entity_type: "quote",
        entity_id: quoteId,
        parent_quote_id: quoteId,
        storage_path: storagePath,
        original_filename: file.name,
        file_size_bytes: file.size,
        mime_type: file.type || null,
        document_type: documentType,
        description: description || null,
        uploaded_by: userId,
        status: "final", // Direct uploads are intentional official documents
      });
      if (insertError) {
        throw new Error(`Ошибка сохранения записи: ${insertError.message}`);
      }

      toast.success(`Файл "${file.name}" загружен`);
      setDescription("");
      setDocumentType("other");
      if (fileInputRef.current) fileInputRef.current.value = "";
      onUploaded();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Неизвестная ошибка";
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="border-2 border-dashed border-border rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <Upload size={16} />
        Загрузить документ
      </div>
      <div className="grid grid-cols-[1fr_1fr_auto] gap-3 items-end">
        <div>
          <Label className="text-xs text-muted-foreground">Тип документа</Label>
          <Select value={documentType} onValueChange={(v) => setDocumentType(v ?? "other")}>
            <SelectTrigger className="h-9 text-sm mt-1">
              <SelectValue>
                {DOCUMENT_TYPE_LABELS[documentType] ?? documentType}
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
        <div>
          <Label className="text-xs text-muted-foreground">
            Описание (необязательно)
          </Label>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Краткое описание"
            className="h-9 text-sm mt-1"
          />
        </div>
        <div>
          <Button
            variant="outline"
            size="sm"
            className="relative h-9"
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Upload size={14} />
            )}
            Выбрать файл
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx"
            onChange={handleUpload}
          />
        </div>
      </div>
    </div>
  );
}
