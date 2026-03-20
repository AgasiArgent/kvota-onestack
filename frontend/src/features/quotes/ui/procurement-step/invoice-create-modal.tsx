"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { QuoteItemRow } from "@/entities/quote/queries";

const CURRENCIES = ["USD", "EUR", "CNY", "RUB"] as const;

interface Supplier {
  id: string;
  name: string;
}

interface BuyerCompany {
  id: string;
  name: string;
  company_code: string;
}

interface InvoiceCreateModalProps {
  open: boolean;
  onClose: () => void;
  selectedItems: QuoteItemRow[];
  suppliers: Supplier[];
  buyerCompanies: BuyerCompany[];
}

export function InvoiceCreateModal({
  open,
  onClose,
  selectedItems,
  suppliers,
  buyerCompanies,
}: InvoiceCreateModalProps) {
  const [supplierId, setSupplierId] = useState("");
  const [buyerCompanyId, setBuyerCompanyId] = useState("");
  const [city, setCity] = useState("");
  const [currency, setCurrency] = useState<string>("USD");
  const [totalWeight, setTotalWeight] = useState("");
  const [totalVolume, setTotalVolume] = useState("");

  function handleClose() {
    resetForm();
    onClose();
  }

  function resetForm() {
    setSupplierId("");
    setBuyerCompanyId("");
    setCity("");
    setCurrency("USD");
    setTotalWeight("");
    setTotalVolume("");
  }

  function handleSubmit() {
    console.log("Create invoice:", {
      supplierId,
      buyerCompanyId,
      city,
      currency,
      totalWeight: totalWeight ? parseFloat(totalWeight) : null,
      totalVolume: totalVolume ? parseFloat(totalVolume) : null,
      itemIds: selectedItems.map((i) => i.id),
    });
    handleClose();
  }

  const canSubmit = supplierId !== "";

  return (
    <Dialog open={open} onOpenChange={(val) => !val && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Создать инвойс</DialogTitle>
          <DialogDescription>
            Заполните данные инвойса и назначьте позиции
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>
              Поставщик <span className="text-destructive">*</span>
            </Label>
            <select
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            >
              <option value="">Выберите поставщика</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label>Компания-покупатель</Label>
            <select
              value={buyerCompanyId}
              onChange={(e) => setBuyerCompanyId(e.target.value)}
              className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            >
              <option value="">Выберите компанию</option>
              {buyerCompanies.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.company_code})
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label>Город</Label>
            <Input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Город отгрузки"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Валюта</Label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Общий вес (кг)</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={totalWeight}
                onChange={(e) => setTotalWeight(e.target.value)}
                placeholder="0.00"
              />
            </div>
            <div className="space-y-1.5">
              <Label>
                Общий объём (м<sup>3</sup>)
              </Label>
              <Input
                type="number"
                step="0.001"
                min="0"
                value={totalVolume}
                onChange={(e) => setTotalVolume(e.target.value)}
                placeholder="0.000"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Файл инвойса</Label>
            <Input type="file" accept=".pdf,.jpg,.png,.xlsx" />
          </div>

          {selectedItems.length > 0 && (
            <div className="space-y-1.5">
              <Label>
                Назначаемые позиции ({selectedItems.length})
              </Label>
              <div className="max-h-36 overflow-y-auto rounded-md border border-input bg-muted/30 p-2 space-y-1">
                {selectedItems.map((item) => (
                  <div
                    key={item.id}
                    className="text-xs flex items-center gap-2"
                  >
                    <span className="font-medium truncate max-w-20">
                      {item.brand ?? "\u2014"}
                    </span>
                    <span className="font-mono text-muted-foreground truncate max-w-24">
                      {item.idn_sku ?? "\u2014"}
                    </span>
                    <span className="truncate flex-1">
                      {item.product_name}
                    </span>
                    <span className="font-mono shrink-0">
                      {item.quantity}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Отмена
          </Button>
          <Button
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            Создать
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
