"use client";

import { useState, useEffect, useRef } from "react";
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
import { Loader2, Upload, FileText, X } from "lucide-react";
import type { CustomerContract } from "@/entities/customer";
import {
  createContract,
  updateContract,
  uploadCustomerDocument,
} from "@/entities/customer/mutations";
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
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setForm(contract ? contractToFormData(contract) : EMPTY_FORM);
      setError(null);
      setPendingFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
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
      // Attach the file (if any) AFTER the contract row exists. Failure
      // here surfaces a separate error so the user knows the contract
      // saved but the file did not — they can retry the upload from the
      // Documents tab.
      if (pendingFile) {
        await uploadCustomerDocument(
          customerId,
          pendingFile,
          "contract",
          form.contract_number
            ? `Договор ${form.contract_number}`
            : undefined
        );
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

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) setPendingFile(file);
  }

  function clearPendingFile() {
    setPendingFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
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

          {/* File upload (attached on save) */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="contract-file"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Файл договора
            </Label>
            {pendingFile ? (
              <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-sidebar/40 px-3 py-2 text-sm">
                <span className="flex min-w-0 items-center gap-2 truncate">
                  <FileText size={14} className="shrink-0 text-text-muted" />
                  <span className="truncate" title={pendingFile.name}>
                    {pendingFile.name}
                  </span>
                  <span className="shrink-0 text-xs text-text-subtle tabular-nums">
                    {Math.round(pendingFile.size / 1024)} КБ
                  </span>
                </span>
                <button
                  type="button"
                  onClick={clearPendingFile}
                  className="shrink-0 rounded p-1 text-text-subtle hover:bg-sidebar hover:text-error"
                  title="Убрать файл"
                  data-testid="contract-file-clear"
                >
                  <X size={14} />
                </button>
              </div>
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                className="self-start"
                data-testid="contract-file-pick"
              >
                <Upload size={14} />
                Выбрать файл
              </Button>
            )}
            <input
              id="contract-file"
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx"
              onChange={handleFileChange}
              data-testid="contract-file-input"
            />
            {isEditing && (
              <p className="text-xs text-text-subtle">
                Файлы, прикреплённые ранее, доступны на вкладке «Документы».
              </p>
            )}
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
