"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { createClient } from "@/shared/lib/supabase/client";
import { createCustomer } from "@/entities/customer/mutations";

interface DaDataResult {
  found: boolean;
  name?: string;
  kpp?: string | null;
  ogrn?: string | null;
  address?: string | null;
  director?: string | null;
  is_active?: boolean;
}

interface CreateCustomerDialogProps {
  orgId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatAutoName(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `Новый клиент ${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
}

export function CreateCustomerDialog({
  orgId,
  open,
  onOpenChange,
}: CreateCustomerDialogProps) {
  const router = useRouter();

  const [inn, setInn] = useState("");
  const [name, setName] = useState("");
  const [kpp, setKpp] = useState("");
  const [ogrn, setOgrn] = useState("");
  const [address, setAddress] = useState("");
  const [director, setDirector] = useState("");
  const [isActive, setIsActive] = useState(true);

  const [noInn, setNoInn] = useState(false);
  const [lookingUp, setLookingUp] = useState(false);
  const [dadataResult, setDadataResult] = useState<DaDataResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [duplicate, setDuplicate] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setInn("");
      setName("");
      setKpp("");
      setOgrn("");
      setAddress("");
      setDirector("");
      setIsActive(true);
      setNoInn(false);
      setLookingUp(false);
      setDadataResult(null);
      setSubmitting(false);
      setDuplicate(null);
    }
  }, [open]);

  // When "no INN" is toggled on, generate auto-name
  useEffect(() => {
    if (noInn) {
      setInn("");
      setDadataResult(null);
      setDuplicate(null);
      setKpp("");
      setOgrn("");
      setAddress("");
      setDirector("");
      setName(formatAutoName());
    } else {
      setName("");
    }
  }, [noInn]);

  const lookupInn = useCallback(async (innValue: string) => {
    const cleaned = innValue.replace(/\D/g, "");
    if (cleaned.length < 10) {
      setDadataResult(null);
      setDuplicate(null);
      return;
    }

    setLookingUp(true);
    setDadataResult(null);
    setDuplicate(null);

    try {
      const res = await fetch("/proxy/dadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inn: cleaned }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setDadataResult({ found: false });
        if (err.error) {
          toast.error(err.error);
        }
        return;
      }

      const data: DaDataResult = await res.json();
      setDadataResult(data);

      if (data.found) {
        setName(data.name ?? "");
        setKpp(data.kpp ?? "");
        setOgrn(data.ogrn ?? "");
        setAddress(data.address ?? "");
        setDirector(data.director ?? "");
        setIsActive(data.is_active ?? true);
      }
    } catch {
      setDadataResult({ found: false });
    } finally {
      setLookingUp(false);
    }
  }, []);

  function handleInnChange(value: string) {
    const cleaned = value.replace(/\D/g, "");
    setInn(cleaned);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (cleaned.length >= 10) {
      debounceRef.current = setTimeout(() => {
        lookupInn(cleaned);
      }, 300);
    } else {
      setDadataResult(null);
      setDuplicate(null);
      setName("");
      setKpp("");
      setOgrn("");
      setAddress("");
      setDirector("");
    }
  }

  async function checkDuplicate(
    innValue: string
  ): Promise<{ id: string; name: string } | null> {
    if (!innValue) return null;

    const supabase = createClient();
    const { data } = await supabase
      .from("customers")
      .select("id, name")
      .eq("inn", innValue)
      .eq("organization_id", orgId)
      .limit(1);

    if (data && data.length > 0) {
      return { id: data[0].id, name: data[0].name };
    }
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Введите название компании");
      return;
    }

    setSubmitting(true);
    try {
      // Check for duplicate INN
      if (!noInn && inn.trim()) {
        const existing = await checkDuplicate(inn.trim());
        if (existing) {
          setDuplicate(existing);
          setSubmitting(false);
          return;
        }
      }

      const result = await createCustomer(orgId, {
        name: trimmedName,
        inn: noInn ? undefined : inn.trim() || undefined,
        kpp: kpp || undefined,
        ogrn: ogrn || undefined,
        legal_address: address || undefined,
      });

      onOpenChange(false);
      router.push(`/customers/${result.id}`);
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка создания клиента";
      if (message.includes("duplicate") || message.includes("unique")) {
        toast.error("Клиент с таким ИНН уже существует");
      } else {
        toast.error(message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  const dadataFound = dadataResult?.found === true;
  const dadataNotFound =
    dadataResult !== null && !dadataResult.found && !lookingUp;
  const canSubmit =
    name.trim().length > 0 && !submitting && !lookingUp && !duplicate;

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Новый клиент</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* No-INN toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <Checkbox
              checked={noInn}
              onCheckedChange={(checked) => setNoInn(checked === true)}
            />
            <span className="text-sm text-text-secondary">
              Не знаю ИНН
            </span>
          </label>

          {/* INN field */}
          {!noInn && (
            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="customer-inn"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                ИНН <span className="text-error">*</span>
              </Label>
              <div className="relative">
                <Input
                  id="customer-inn"
                  value={inn}
                  onChange={(e) => handleInnChange(e.target.value)}
                  placeholder="10 или 12 цифр"
                  inputMode="numeric"
                  maxLength={12}
                  autoFocus
                />
                {lookingUp && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <Loader2 size={16} className="animate-spin text-text-muted" />
                  </div>
                )}
                {dadataFound && !lookingUp && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <CheckCircle2 size={16} className="text-green-600" />
                  </div>
                )}
                {dadataNotFound && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <AlertTriangle size={16} className="text-amber-500" />
                  </div>
                )}
              </div>

              {dadataNotFound && (
                <p className="text-xs text-amber-600">
                  ИНН не найден в DaData. Заполните название вручную.
                </p>
              )}

              {dadataFound && !isActive && (
                <p className="text-xs text-red-600">
                  Компания ликвидирована
                </p>
              )}
            </fieldset>
          )}

          {/* Duplicate warning */}
          {duplicate && (
            <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
              <p>
                Клиент с ИНН {inn} уже существует: <strong>{duplicate.name}</strong>
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={() => {
                  onOpenChange(false);
                  router.push(`/customers/${duplicate.id}`);
                }}
              >
                Открыть карточку
              </Button>
            </div>
          )}

          {/* Company name */}
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
              readOnly={dadataFound}
              className={dadataFound ? "bg-muted" : ""}
              autoFocus={noInn}
            />
          </fieldset>

          {/* Auto-filled fields from DaData */}
          {dadataFound && (
            <div className="rounded-md bg-green-50 border border-green-200 p-3 flex flex-col gap-2">
              {kpp && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-text-muted min-w-[4rem]">КПП</span>
                  <span className="text-text-primary font-medium">{kpp}</span>
                </div>
              )}
              {ogrn && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-text-muted min-w-[4rem]">ОГРН</span>
                  <span className="text-text-primary font-medium">{ogrn}</span>
                </div>
              )}
              {address && (
                <div className="flex items-start gap-2 text-sm">
                  <span className="text-text-muted min-w-[4rem] shrink-0">
                    Адрес
                  </span>
                  <span className="text-text-primary">{address}</span>
                </div>
              )}
              {director && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-text-muted min-w-[4rem]">Рук-ль</span>
                  <span className="text-text-primary">{director}</span>
                </div>
              )}
            </div>
          )}

          {/* Manual name entry hint when DaData not found */}
          {dadataNotFound && !name && (
            <p className="text-xs text-text-muted">
              Введите название компании вручную
            </p>
          )}

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
              disabled={!canSubmit}
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
