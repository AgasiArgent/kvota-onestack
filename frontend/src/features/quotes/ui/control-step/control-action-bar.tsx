"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, RotateCcw, Clock, Loader2, FileDown } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { config } from "@/shared/config";
import {
  approveQuote,
  escalateQuote,
} from "@/entities/quote/mutations";
import { ReturnSheetDialog } from "./return-sheet-dialog";

interface ControlActionBarProps {
  quoteId: string;
  userId: string;
  workflowStatus: string;
  needsApproval: boolean;
}

export function ControlActionBar({
  quoteId,
  userId,
  workflowStatus,
  needsApproval,
}: ControlActionBarProps) {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [returnSheetOpen, setReturnSheetOpen] = useState(false);

  if (
    workflowStatus !== "pending_quote_control" &&
    workflowStatus !== "pending_approval"
  ) {
    return null;
  }

  async function handleApprove() {
    setLoading("approve");
    try {
      await approveQuote(quoteId, userId);
      toast.success("КП одобрено");
      router.refresh();
    } catch {
      toast.error("Не удалось одобрить КП");
    } finally {
      setLoading(null);
    }
  }

  async function handleEscalate() {
    setLoading("escalate");
    try {
      await escalateQuote(quoteId, userId, "");
      toast.success("КП отправлено на согласование");
      router.refresh();
    } catch {
      toast.error("Не удалось отправить на согласование");
    } finally {
      setLoading(null);
    }
  }

  function handleReturnSuccess() {
    router.refresh();
  }

  return (
    <>
      <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-card shadow-[0_-2px_10px_rgba(0,0,0,0.05)]">
        <div className="mx-auto flex max-w-screen-xl items-center gap-2 px-6 py-3">
          <Button
            size="sm"
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleApprove}
            disabled={loading !== null}
          >
            {loading === "approve" ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Check size={14} />
            )}
            Одобрить
          </Button>

          {workflowStatus === "pending_quote_control" && (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setReturnSheetOpen(true)}
                disabled={loading !== null}
              >
                <RotateCcw size={14} />
                Вернуть на доработку
              </Button>

              {needsApproval && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleEscalate}
                  disabled={loading !== null}
                >
                  {loading === "escalate" ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Clock size={14} />
                  )}
                  На согласование
                </Button>
              )}
            </>
          )}

          <div className="ml-auto flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => window.open(`/export/kp/${quoteId}`, "_blank")}
            >
              <FileDown size={14} />
              КП PDF
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => window.open(`${config.legacyAppUrl}/quotes/${quoteId}/export/validation`, "_blank")}
            >
              <FileDown size={14} />
              Validation Excel
            </Button>
          </div>
        </div>
      </div>

      <ReturnSheetDialog
        quoteId={quoteId}
        userId={userId}
        open={returnSheetOpen}
        onOpenChange={setReturnSheetOpen}
        onSuccess={handleReturnSuccess}
      />
    </>
  );
}
