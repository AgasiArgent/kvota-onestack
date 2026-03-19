"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { UserSelect } from "./user-select";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgId: string;
  initialBrand?: string;
  onSubmit: (brand: string, userId: string) => Promise<void>;
}

export function BrandAssignmentDialog({
  open,
  onOpenChange,
  orgId,
  initialBrand = "",
  onSubmit,
}: Props) {
  const [brand, setBrand] = useState(initialBrand);
  const [userId, setUserId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setBrand(initialBrand);
      setUserId("");
    }
  }, [open, initialBrand]);

  async function handleSubmit() {
    const trimmed = brand.trim();
    if (!trimmed || !userId) return;

    setSubmitting(true);
    try {
      await onSubmit(trimmed, userId);
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !submitting && onOpenChange(val)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Назначить бренд</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Бренд <span className="text-error">*</span>
            </Label>
            <Input
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              placeholder="Название бренда"
              autoFocus={!initialBrand}
            />
          </fieldset>
          <fieldset className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Менеджер закупок <span className="text-error">*</span>
            </Label>
            <UserSelect
              value={userId}
              onValueChange={setUserId}
              orgId={orgId}
            />
          </fieldset>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!brand.trim() || !userId || submitting}
            className="bg-accent text-white hover:bg-accent-hover"
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Назначить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
