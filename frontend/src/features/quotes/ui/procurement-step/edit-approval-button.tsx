"use client";

import { useState } from "react";
import { Loader2, PenLine } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { requestEditApproval } from "@/entities/invoice/mutations";

interface EditApprovalButtonProps {
  invoiceId: string;
}

export function EditApprovalButton({ invoiceId }: EditApprovalButtonProps) {
  const [requesting, setRequesting] = useState(false);
  const [requested, setRequested] = useState(false);

  async function handleRequest() {
    setRequesting(true);
    try {
      await requestEditApproval(invoiceId);
      setRequested(true);
      toast.success("Запрос на одобрение отправлен");
    } catch {
      toast.error("Не удалось отправить запрос");
    } finally {
      setRequesting(false);
    }
  }

  if (requested) {
    return (
      <span className="text-xs text-muted-foreground">
        Запрос отправлен
      </span>
    );
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      className="text-xs text-muted-foreground"
      onClick={handleRequest}
      disabled={requesting}
      title="Запросить разрешение на редактирование"
    >
      {requesting ? (
        <Loader2 size={14} className="animate-spin mr-1" />
      ) : (
        <PenLine size={14} className="mr-1" />
      )}
      Редактировать с одобрением
    </Button>
  );
}
