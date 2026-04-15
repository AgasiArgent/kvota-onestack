"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Undo2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { restoreQuote } from "@/entities/quote/mutations";

interface TrashRestoreButtonProps {
  quoteId: string;
  quoteIdn: string;
}

export function TrashRestoreButton({
  quoteId,
  quoteIdn,
}: TrashRestoreButtonProps) {
  const router = useRouter();
  const [isRestoring, setIsRestoring] = useState(false);

  async function handleRestore() {
    setIsRestoring(true);
    try {
      await restoreQuote(quoteId);
      toast.success(`Квота ${quoteIdn} восстановлена`);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Restore failed");
      setIsRestoring(false);
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleRestore}
      disabled={isRestoring}
    >
      {isRestoring ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      ) : (
        <Undo2 className="mr-2 h-4 w-4" />
      )}
      Восстановить
    </Button>
  );
}
