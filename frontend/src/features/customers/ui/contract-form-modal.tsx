"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import type { CustomerContract } from "@/entities/customer";
import { createContract, updateContract } from "@/entities/customer/mutations";
import type { ContractFormData } from "@/entities/customer";

interface ContractFormModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  customerId: string;
  contract?: CustomerContract;
}

const EMPTY_FORM: ContractFormData = {
  contract_number: "",
  contract_date: "",
  status: "active",
  notes: "",
};

const STATUS_OPTIONS: { value: ContractFormData["status"]; label: string }[] = [
  { value: "active", label: "Действующий" },
  { value: "suspended", label: "Приостановлен" },
  { value: "terminated", label: "Расторгнут" },
];

function contractToFormData(contract: CustomerContract): ContractFormData {
  return {
    contract_number: contract.contract_number,
    contract_date: contract.contract_date ?? "",
    status: contract.status,
    notes: contract.notes ?? "",
  };
}

export function ContractFormModal({
  open,
  onClose,
  onSaved,
  customerId,
  contract,
}: ContractFormModalProps) {
  const router = useRouter();
  const isEditing = !!contract;

  const [form, setForm] = useState<ContractFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setForm(contract ? contractToFormData(contract) : EMPTY_FORM);
      setError(null);
    }
  }, [open, contract]);

  function updateField<K extends keyof ContractFormData>(
    key: K,
    value: ContractFormData[K]
  ) {
    setForm((prev: ContractFormData) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!form.contract_number.trim()) {
      setError("Номер договора обязателен для заполнения");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      if (isEditing) {
        await updateContract(contract.id, form);
      } else {
        await createContract(customerId, form);
      }
      router.refresh();
      onSaved();
      onClose();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка при сохранении";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Редактировать договор" : "Новый договор"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Contract number (required) */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="contract-number"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Номер договора <span className="text-error">*</span>
            </Label>
            <Input
              id="contract-number"
              value={form.contract_number}
              onChange={(e) => updateField("contract_number", e.target.value)}
              placeholder="Д-2026/001"
              autoFocus
            />
          </fieldset>

          {/* Date + Status row */}
          <div className="grid grid-cols-2 gap-3">
            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="contract-date"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Дата договора
              </Label>
              <Input
                id="contract-date"
                type="date"
                value={form.contract_date}
                onChange={(e) => updateField("contract_date", e.target.value)}
              />
            </fieldset>

            <fieldset className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Статус
              </Label>
              <Select
                value={form.status}
                onValueChange={(val) =>
                  updateField("status", val as ContractFormData["status"])
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </fieldset>
          </div>

          {/* Notes */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="contract-notes"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Заметки
            </Label>
            <Textarea
              id="contract-notes"
              value={form.notes}
              onChange={(e) => updateField("notes", e.target.value)}
              placeholder="Дополнительная информация"
              rows={2}
            />
          </fieldset>

          {/* Error message */}
          {error && <p className="text-xs text-error">{error}</p>}

          {/* Footer */}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={saving}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={saving}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {saving && <Loader2 className="animate-spin" />}
              Сохранить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
