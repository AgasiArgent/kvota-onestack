"use client";

/**
 * QA verify-button row (Tasks 23 + 24 — Req 9.1–9.8).
 *
 * Rendered inside each QA pin's drawer row (see `pin-list-section.tsx`) and
 * inside the pin-popover on the annotated-screen overlay. Emits one INSERT
 * per click against `kvota.journey_verifications` (append-only — RLS denies
 * UPDATE and DELETE for every role, Req 9.2).
 *
 * Task 24 adds screenshot attachments for "broken" verifications:
 *   - Up to 3 image files (png/jpeg/webp, 2 MB each).
 *   - Client validates on file-pick and shows a toast per rejection.
 *   - Files upload to `journey-verification-attachments` bucket FIRST; on
 *     success, the INSERT writes the storage keys to `attachment_urls`.
 *     Partial attachment is not permitted (Req 9.6) — a single upload
 *     failure aborts the INSERT and cleans up already-uploaded keys.
 *
 * Visibility is gated on {@link shouldShowVerifyButtons}: training-mode pins
 * never get verify buttons (Req 8 note 7), and only `admin` / `quote_controller`
 * / `spec_controller` may record verifications (Req 9.2 + `access.ts`).
 */

import { useRef, useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import {
  JOURNEY_QUERY_KEYS,
  createVerification,
  type JourneyNodeId,
  type JourneyPin,
  type RoleSlug,
  type VerifyResult,
} from "@/entities/journey";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { createClient } from "@/shared/lib/supabase/client";

import {
  ALLOWED_MIME,
  ATTACHMENT_BUCKET,
  MAX_ATTACHMENTS,
  uploadAttachments,
  validateAttachments,
  type AttachmentRejection,
} from "@/features/journey/lib/attachment-upload";

import {
  buildVerificationPayload,
  classifyVerifyError,
  shouldShowVerifyButtons,
} from "./_verify-helpers";

const BROKEN_NOTE_MIN = 5;

const REJECT_LABEL: Record<AttachmentRejection["reason"], string> = {
  bad_mime: "Неподдерживаемый формат",
  too_large: "Файл больше 2 МБ",
  over_limit: `Не более ${MAX_ATTACHMENTS} файлов`,
};

/** Safe filename segment for the storage key prefix. */
function nodeIdToSafeSegment(nodeId: JourneyNodeId): string {
  return nodeId.replace(/[^A-Za-z0-9._-]+/g, "_");
}

export interface VerifyButtonsProps {
  readonly pin: JourneyPin;
  readonly nodeId: JourneyNodeId;
  readonly userId: string;
  readonly userRoles: readonly RoleSlug[];
}

export function VerifyButtons({
  pin,
  nodeId,
  userId,
  userRoles,
}: VerifyButtonsProps) {
  const qc = useQueryClient();
  const [submitting, setSubmitting] = useState<VerifyResult | null>(null);
  const [brokenOpen, setBrokenOpen] = useState(false);
  const [note, setNote] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  if (!shouldShowVerifyButtons(pin, userRoles)) return null;

  const handleFilePick = (picked: FileList | null) => {
    if (!picked || picked.length === 0) return;
    const { valid, rejected } = validateAttachments(
      Array.from(picked),
      attachments.length,
    );
    for (const r of rejected) {
      toast.error(`${r.file.name}: ${REJECT_LABEL[r.reason]}`);
    }
    if (valid.length > 0) {
      setAttachments((prev) => [...prev, ...valid]);
    }
    // Reset input so the user can re-pick the same file after removing it.
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeAttachment = (idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  };

  const record = async (result: VerifyResult, rawNote?: string) => {
    setSubmitting(result);

    // Attachments only apply to broken flow. The `verified` / `skip` buttons
    // don't collect files, so `attachments` is always empty for them.
    let attachmentPaths: string[] = [];
    if (attachments.length > 0) {
      const supabase = createClient();
      const keyPrefix = `${nodeIdToSafeSegment(nodeId)}/${pin.id}`;
      const uploadResult = await uploadAttachments(attachments, {
        bucket: ATTACHMENT_BUCKET,
        keyPrefix,
        supabaseUpload: (path, file) =>
          supabase.storage
            .from(ATTACHMENT_BUCKET)
            .upload(path, file, { contentType: file.type }),
        supabaseRemove: (paths) =>
          supabase.storage.from(ATTACHMENT_BUCKET).remove(paths),
      });
      if (!uploadResult.success) {
        setSubmitting(null);
        toast.error(
          `Не удалось загрузить вложения: ${uploadResult.reason}`,
        );
        return;
      }
      attachmentPaths = uploadResult.paths;
    }

    const payload = buildVerificationPayload({
      pinId: pin.id,
      nodeId,
      result,
      note: rawNote ?? null,
      testedBy: userId,
      attachmentUrls: attachmentPaths.length > 0 ? attachmentPaths : null,
    });
    const { error } = await createVerification(payload);
    setSubmitting(null);
    if (error) {
      toast.error(classifyVerifyError(error).userMessage);
      return;
    }
    toast.success("Верификация записана");
    qc.invalidateQueries({ queryKey: JOURNEY_QUERY_KEYS.nodeDetail(nodeId) });
    setBrokenOpen(false);
    setNote("");
    setAttachments([]);
  };

  const onBrokenSubmit = () => {
    if (note.trim().length < BROKEN_NOTE_MIN) return;
    void record("broken", note);
  };

  const canAddMore = attachments.length < MAX_ATTACHMENTS;

  return (
    <div
      data-testid={`verify-buttons-${pin.id}`}
      className="flex flex-col gap-1.5"
    >
      <div className="flex flex-wrap gap-1.5">
        <Button
          size="sm"
          variant="outline"
          disabled={submitting !== null}
          onClick={() => void record("verified")}
          data-testid={`verify-btn-verified-${pin.id}`}
          className="border-success text-success hover:bg-success-subtle"
        >
          {submitting === "verified" ? "…" : "✓ Верифицировано"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={submitting !== null}
          onClick={() => setBrokenOpen((v) => !v)}
          data-testid={`verify-btn-broken-${pin.id}`}
          className="border-destructive text-destructive hover:bg-destructive/10"
        >
          ✗ Сломано
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={submitting !== null}
          onClick={() => void record("skip")}
          data-testid={`verify-btn-skip-${pin.id}`}
        >
          {submitting === "skip" ? "…" : "Пропустить"}
        </Button>
      </div>
      {brokenOpen && (
        <div
          data-testid={`verify-broken-note-${pin.id}`}
          className="flex flex-col gap-1.5"
        >
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Что сломано? (не менее 5 символов)"
            rows={2}
            className="text-xs"
          />
          <div className="flex flex-col gap-1">
            <label className="flex items-center gap-1.5 text-[11px] text-text-subtle">
              <input
                ref={fileInputRef}
                type="file"
                accept={ALLOWED_MIME.join(",")}
                multiple
                disabled={!canAddMore || submitting !== null}
                onChange={(e) => handleFilePick(e.target.files)}
                data-testid={`verify-broken-files-${pin.id}`}
                className="text-[11px]"
              />
              <span>
                Скриншоты ({attachments.length}/{MAX_ATTACHMENTS}, ≤ 2 МБ)
              </span>
            </label>
            {attachments.length > 0 && (
              <ul
                data-testid={`verify-broken-attachments-${pin.id}`}
                className="flex flex-col gap-0.5"
              >
                {attachments.map((f, i) => (
                  <li
                    key={`${f.name}-${i}`}
                    className="flex items-center justify-between text-[11px] text-text"
                  >
                    <span className="truncate">{f.name}</span>
                    <button
                      type="button"
                      onClick={() => removeAttachment(i)}
                      disabled={submitting !== null}
                      className="ml-2 text-text-subtle hover:text-destructive"
                      aria-label={`Удалить ${f.name}`}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="flex gap-1.5">
            <Button
              size="sm"
              disabled={
                submitting !== null || note.trim().length < BROKEN_NOTE_MIN
              }
              onClick={onBrokenSubmit}
              data-testid={`verify-broken-submit-${pin.id}`}
            >
              {submitting === "broken" ? "Запись…" : "Записать"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={submitting !== null}
              onClick={() => {
                setBrokenOpen(false);
                setNote("");
                setAttachments([]);
              }}
            >
              Отмена
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
