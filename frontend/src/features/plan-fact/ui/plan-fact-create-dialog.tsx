"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  fetchPlanFactCategories,
  createPlanFactItem,
} from "@/features/plan-fact/api";
import { QuoteSearch } from "./quote-search";
import type {
  PlanFactCategory,
  PlanFactCurrency,
  QuoteSearchResult,
} from "@/entities/finance";

interface PlanFactCreateDialogProps {
  dealId?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
  showQuoteSearch?: boolean;
}

const CURRENCY_OPTIONS: { value: PlanFactCurrency; label: string }[] = [
  { value: "RUB", label: "RUB" },
  { value: "USD", label: "USD" },
  { value: "EUR", label: "EUR" },
];

interface CategoryGroup {
  label: string;
  items: PlanFactCategory[];
}

function groupCategories(categories: PlanFactCategory[]): CategoryGroup[] {
  const groups: CategoryGroup[] = [
    { label: "Доходы", items: [] },
    { label: "Поставщик", items: [] },
    { label: "Логистика", items: [] },
    { label: "Таможня", items: [] },
    { label: "Прочее", items: [] },
  ];

  for (const cat of categories) {
    if (cat.is_income) {
      groups[0].items.push(cat);
    } else if (cat.code.startsWith("supplier_")) {
      groups[1].items.push(cat);
    } else if (cat.code.startsWith("logistics_")) {
      groups[2].items.push(cat);
    } else if (cat.code.startsWith("customs_")) {
      groups[3].items.push(cat);
    } else {
      groups[4].items.push(cat);
    }
  }

  return groups.filter((g) => g.items.length > 0);
}

function getTodayISO(): string {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

interface FormErrors {
  category_id?: string;
  description?: string;
  planned_amount?: string;
  planned_date?: string;
  deal_id?: string;
}

export function PlanFactCreateDialog({
  dealId: dealIdProp,
  open,
  onOpenChange,
  onSuccess,
  showQuoteSearch = false,
}: PlanFactCreateDialogProps) {
  // Categories
  const [categories, setCategories] = useState<PlanFactCategory[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(false);

  // Form state
  const [categoryId, setCategoryId] = useState("");
  const [description, setDescription] = useState("");
  const [plannedAmount, setPlannedAmount] = useState("");
  const [plannedCurrency, setPlannedCurrency] =
    useState<PlanFactCurrency>("RUB");
  const [plannedDate, setPlannedDate] = useState(getTodayISO());

  // Quote search state (when showQuoteSearch is true)
  const [selectedDealId, setSelectedDealId] = useState<string | null>(null);

  // Submission
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  const effectiveDealId = dealIdProp ?? selectedDealId;

  // Fetch categories on mount
  useEffect(() => {
    if (!open) return;

    let cancelled = false;

    async function loadCategories() {
      setLoadingCategories(true);
      try {
        const data = await fetchPlanFactCategories();
        if (!cancelled) {
          setCategories(data);
        }
      } catch {
        if (!cancelled) {
          toast.error("Не удалось загрузить категории");
        }
      } finally {
        if (!cancelled) {
          setLoadingCategories(false);
        }
      }
    }

    loadCategories();

    return () => {
      cancelled = true;
    };
  }, [open]);

  function resetForm() {
    setCategoryId("");
    setDescription("");
    setPlannedAmount("");
    setPlannedCurrency("RUB");
    setPlannedDate(getTodayISO());
    setSelectedDealId(null);
    setErrors({});
  }

  function validate(): FormErrors {
    const errs: FormErrors = {};
    if (!categoryId) {
      errs.category_id = "Выберите категорию";
    }
    const parsed = parseFloat(plannedAmount);
    if (!plannedAmount || isNaN(parsed) || parsed <= 0) {
      errs.planned_amount = "Введите корректную сумму";
    }
    if (!plannedDate) {
      errs.planned_date = "Укажите дату";
    }
    if (!effectiveDealId) {
      errs.deal_id = "Выберите КП со сделкой";
    }
    return errs;
  }

  async function handleSubmit() {
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    if (!effectiveDealId) return;

    setErrors({});
    setSubmitting(true);

    try {
      await createPlanFactItem(effectiveDealId, {
        category_id: categoryId,
        description: description.trim(),
        planned_amount: parseFloat(plannedAmount),
        planned_currency: plannedCurrency,
        planned_date: plannedDate,
      });
      resetForm();
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось создать платёж";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetForm();
    }
    onOpenChange(nextOpen);
  }

  function handleQuoteSelect(result: QuoteSearchResult) {
    setSelectedDealId(result.deal_id);
    if (errors.deal_id) {
      setErrors((prev) => ({ ...prev, deal_id: undefined }));
    }
  }

  const groupedCategories = groupCategories(categories);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Новый платёж</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {/* Quote search (finance page context) */}
          {showQuoteSearch && (
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                КП / Сделка <span className="text-destructive">*</span>
              </Label>
              <QuoteSearch onSelect={handleQuoteSelect} />
              {errors.deal_id && (
                <p className="text-xs text-destructive">{errors.deal_id}</p>
              )}
            </div>
          )}

          {/* Category (grouped dropdown) */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Категория <span className="text-destructive">*</span>
            </Label>
            {loadingCategories ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground h-8">
                <Loader2 size={14} className="animate-spin" />
                Загрузка...
              </div>
            ) : (
              <Select
                value={categoryId}
                onValueChange={(val) => {
                  setCategoryId(val || "");
                  if (errors.category_id) {
                    setErrors((prev) => ({
                      ...prev,
                      category_id: undefined,
                    }));
                  }
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Выберите категорию" />
                </SelectTrigger>
                <SelectContent>
                  {groupedCategories.map((group) => (
                    <SelectGroup key={group.label}>
                      <SelectLabel>{group.label}</SelectLabel>
                      {group.items.map((cat) => (
                        <SelectItem key={cat.id} value={cat.id}>
                          {cat.name}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </SelectContent>
              </Select>
            )}
            {errors.category_id && (
              <p className="text-xs text-destructive">{errors.category_id}</p>
            )}
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Описание
            </Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Описание платежа..."
            />
          </div>

          {/* Amount + Currency row */}
          <div className="grid grid-cols-[1fr_100px] gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Сумма план <span className="text-destructive">*</span>
              </Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                value={plannedAmount}
                onChange={(e) => {
                  setPlannedAmount(e.target.value);
                  if (errors.planned_amount) {
                    setErrors((prev) => ({
                      ...prev,
                      planned_amount: undefined,
                    }));
                  }
                }}
                placeholder="0.00"
                className={errors.planned_amount ? "border-destructive" : ""}
              />
              {errors.planned_amount && (
                <p className="text-xs text-destructive">
                  {errors.planned_amount}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Валюта
              </Label>
              <Select
                value={plannedCurrency}
                onValueChange={(val) => {
                  if (val) setPlannedCurrency(val as PlanFactCurrency);
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCY_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Planned date */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Дата план <span className="text-destructive">*</span>
            </Label>
            <Input
              type="date"
              value={plannedDate}
              onChange={(e) => {
                setPlannedDate(e.target.value);
                if (errors.planned_date) {
                  setErrors((prev) => ({ ...prev, planned_date: undefined }));
                }
              }}
              className={errors.planned_date ? "border-destructive" : ""}
            />
            {errors.planned_date && (
              <p className="text-xs text-destructive">{errors.planned_date}</p>
            )}
          </div>
        </div>

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
            type="button"
            onClick={handleSubmit}
            disabled={submitting || loadingCategories}
            className="bg-accent text-white hover:bg-accent-hover"
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Создать
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
