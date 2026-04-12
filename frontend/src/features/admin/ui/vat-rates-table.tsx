"use client";

import { useState, useEffect, useCallback } from "react";
import { Check, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetchVatRates, type VatRate } from "@/entities/invoice/queries";
import { updateVatRate } from "@/entities/invoice/mutations";
import { findCountryByCode } from "@/shared/ui/geo";

export function VatRatesTable() {
  const [rates, setRates] = useState<VatRate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingCode, setEditingCode] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);

  const loadRates = useCallback(async () => {
    try {
      const data = await fetchVatRates();
      setRates(data);
    } catch {
      toast.error("Не удалось загрузить ставки НДС");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRates();
  }, [loadRates]);

  function startEditing(rate: VatRate) {
    setEditingCode(rate.country_code);
    setEditValue(rate.rate.toString());
  }

  function cancelEditing() {
    setEditingCode(null);
    setEditValue("");
  }

  async function saveRate(countryCode: string) {
    const parsed = parseFloat(editValue);
    if (isNaN(parsed) || parsed < 0 || parsed > 100) {
      toast.error("Ставка должна быть от 0 до 100");
      return;
    }

    setSaving(true);
    try {
      await updateVatRate(countryCode, parsed);
      // Optimistic update
      setRates((prev) =>
        prev.map((r) =>
          r.country_code === countryCode
            ? { ...r, rate: parsed, updated_at: new Date().toISOString() }
            : r
        )
      );
      setEditingCode(null);
      setEditValue("");
      toast.success("Ставка обновлена");
    } catch {
      toast.error("Не удалось обновить ставку");
    } finally {
      setSaving(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent, countryCode: string) {
    if (e.key === "Enter") {
      saveRate(countryCode);
    } else if (e.key === "Escape") {
      cancelEditing();
    }
  }

  const dateFmt = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={20} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-20">Код</TableHead>
          <TableHead>Страна</TableHead>
          <TableHead className="w-32">Ставка, %</TableHead>
          <TableHead>Примечание</TableHead>
          <TableHead className="w-40">Обновлено</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rates.map((rate) => {
          const country = findCountryByCode(rate.country_code);
          const isEditing = editingCode === rate.country_code;

          return (
            <TableRow key={rate.country_code}>
              <TableCell className="font-mono text-xs">
                {rate.country_code}
              </TableCell>
              <TableCell>{country?.nameRu ?? rate.country_code}</TableCell>
              <TableCell>
                {isEditing ? (
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      step="0.01"
                      min="0"
                      max="100"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e, rate.country_code)}
                      className="h-7 w-20 text-sm tabular-nums"
                      autoFocus
                      disabled={saving}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => saveRate(rate.country_code)}
                      disabled={saving}
                    >
                      {saving ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Check size={12} />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={cancelEditing}
                      disabled={saving}
                    >
                      <X size={12} />
                    </Button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => startEditing(rate)}
                    className="text-sm tabular-nums hover:underline cursor-pointer"
                  >
                    {rate.rate.toFixed(2)}
                  </button>
                )}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {rate.notes ?? "\u2014"}
              </TableCell>
              <TableCell className="text-xs text-muted-foreground tabular-nums">
                {dateFmt.format(new Date(rate.updated_at))}
              </TableCell>
            </TableRow>
          );
        })}
        {rates.length === 0 && (
          <TableRow>
            <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
              Нет данных о ставках НДС
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
