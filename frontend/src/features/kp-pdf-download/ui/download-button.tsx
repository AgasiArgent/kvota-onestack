"use client";

/**
 * Download CTA placed in the КП preview toolbar (REQ-13).
 *
 * Flow:
 * 1. Click → call the Server Action with the current proposal.
 * 2. On success: decode the base64 bytes into a Blob, create an object
 *    URL, trigger an `<a download>` click, then revoke the URL.
 * 3. On failure: show a sonner toast using `parseErrorMessage`; leave
 *    form state untouched per REQ-19 (the user can retry without
 *    re-entering data).
 *
 * While the request is in flight the button is disabled and shows a
 * spinner glyph to prevent double-submission (REQ-13.4).
 */

import { useState, useTransition } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import type { KpProposal } from "@/entities/kp-proposal";
import { Button } from "@/components/ui/button";

import { downloadKpPdf } from "../api/render-pdf-action";
import { parseErrorMessage } from "../api/parse-error";

interface DownloadKpPdfButtonProps {
  data: KpProposal;
}

function base64ToBlob(base64: string, mime: string): Blob {
  const binary = atob(base64);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mime });
}

function todayIso(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } finally {
    // Revoke after a tick — some browsers need the URL alive for the
    // download dialog to register the filename.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export function DownloadKpPdfButton({ data }: DownloadKpPdfButtonProps) {
  const [isPending, startTransition] = useTransition();
  const [isInFlight, setInFlight] = useState(false);

  const handleClick = () => {
    setInFlight(true);
    startTransition(async () => {
      try {
        const result = await downloadKpPdf(data);
        if (!result.ok) {
          toast.error(
            parseErrorMessage({
              code: result.code,
              message: result.message,
              requestId: result.requestId,
            }),
          );
          return;
        }
        const blob = base64ToBlob(result.pdfBase64, "application/pdf");
        triggerBlobDownload(blob, `kp-${todayIso()}.pdf`);
      } catch (e) {
        // Catches Server Action transport errors and any failure inside
        // base64ToBlob / triggerBlobDownload. Without this the user sees
        // the spinner vanish with no PDF and no error.
        console.error("KP download failed", e);
        toast.error(
          "Не удалось сгенерировать PDF, попробуйте ещё раз",
        );
      } finally {
        setInFlight(false);
      }
    });
  };

  const disabled = isPending || isInFlight;

  return (
    <Button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      aria-label="Сохранить PDF"
    >
      {disabled ? (
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
      ) : (
        <Download className="size-3.5" aria-hidden="true" />
      )}
      Сохранить PDF
    </Button>
  );
}
