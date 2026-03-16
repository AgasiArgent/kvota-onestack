"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
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
import { createCustomer } from "@/entities/customer/mutations";

interface CreateCustomerDialogProps {
  orgId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateCustomerDialog({
  orgId,
  open,
  onOpenChange,
}: CreateCustomerDialogProps) {
  const router = useRouter();

  const [name, setName] = useState("");
  const [inn, setInn] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setInn("");
    }
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Введите название компании");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createCustomer(orgId, {
        name: trimmedName,
        inn: inn.trim() || undefined,
      });

      onOpenChange(false);
      router.push(`/customers/${result.id}`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка создания клиента";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Новый клиент</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="customer-name"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Название компании <span className="text-error">*</span>
            </Label>
            <Input
              id="customer-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ООО «Компания»"
              autoFocus
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="customer-inn"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              ИНН
            </Label>
            <Input
              id="customer-inn"
              value={inn}
              onChange={(e) => setInn(e.target.value)}
              placeholder="1234567890"
              inputMode="numeric"
            />
          </fieldset>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || submitting}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Создать клиента
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
