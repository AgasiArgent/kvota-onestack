"use client";

import { useState, useRef, useEffect, useCallback } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  PhmbDefaults,
  SellerCompany,
  CustomerSearchResult,
} from "@/entities/phmb-quote/types";
import {
  createPhmbQuote,
  searchCustomers,
} from "@/entities/phmb-quote/mutations";

interface CreatePhmbDialogProps {
  defaults: PhmbDefaults;
  sellerCompanies: SellerCompany[];
  orgId: string;
  userId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const CURRENCIES = [
  { value: "USD", label: "USD" },
  { value: "EUR", label: "EUR" },
  { value: "CNY", label: "CNY" },
  { value: "RUB", label: "RUB" },
] as const;

export function CreatePhmbDialog({
  defaults,
  sellerCompanies,
  orgId,
  userId,
  open,
  onOpenChange,
}: CreatePhmbDialogProps) {
  const router = useRouter();

  // Form state
  const [selectedCustomer, setSelectedCustomer] =
    useState<CustomerSearchResult | null>(null);
  const [currency, setCurrency] = useState("USD");
  const [sellerCompanyId, setSellerCompanyId] = useState(
    sellerCompanies.length === 1 ? sellerCompanies[0].id : ""
  );
  const [advancePct, setAdvancePct] = useState(
    String(defaults.default_advance_pct)
  );
  const [paymentDays, setPaymentDays] = useState(
    String(defaults.default_payment_days)
  );
  const [markupPct, setMarkupPct] = useState(
    String(defaults.default_markup_pct)
  );

  // Typeahead state
  const [customerQuery, setCustomerQuery] = useState("");
  const [customerResults, setCustomerResults] = useState<
    CustomerSearchResult[]
  >([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchingCustomers, setSearchingCustomers] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Submit state
  const [submitting, setSubmitting] = useState(false);

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setSelectedCustomer(null);
      setCustomerQuery("");
      setCustomerResults([]);
      setCurrency("USD");
      setSellerCompanyId(
        sellerCompanies.length === 1 ? sellerCompanies[0].id : ""
      );
      setAdvancePct(String(defaults.default_advance_pct));
      setPaymentDays(String(defaults.default_payment_days));
      setMarkupPct(String(defaults.default_markup_pct));
    }
  }, [open, defaults, sellerCompanies]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleCustomerSearch = useCallback(
    (value: string) => {
      setCustomerQuery(value);
      setSelectedCustomer(null);

      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (value.length < 2) {
        setCustomerResults([]);
        setShowDropdown(false);
        return;
      }

      debounceRef.current = setTimeout(async () => {
        setSearchingCustomers(true);
        try {
          const results = await searchCustomers(value, orgId);
          setCustomerResults(results);
          setShowDropdown(results.length > 0);
        } catch {
          setCustomerResults([]);
          setShowDropdown(false);
        } finally {
          setSearchingCustomers(false);
        }
      }, 300);
    },
    [orgId]
  );

  function handleSelectCustomer(customer: CustomerSearchResult) {
    setSelectedCustomer(customer);
    setCustomerQuery(customer.name);
    setShowDropdown(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!selectedCustomer) {
      toast.error("Выберите клиента");
      return;
    }
    if (!currency) {
      toast.error("Выберите валюту");
      return;
    }
    if (!sellerCompanyId) {
      toast.error("Выберите юрлицо");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createPhmbQuote(orgId, userId, {
        customer_id: selectedCustomer.id,
        currency,
        seller_company_id: sellerCompanyId,
        phmb_advance_pct: parseFloat(advancePct) || 0,
        phmb_payment_days: parseInt(paymentDays, 10) || 30,
        phmb_markup_pct: parseFloat(markupPct) || 10,
      });

      onOpenChange(false);
      router.push(`/phmb/${result.id}`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка создания КП";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  const isValid = !!selectedCustomer && !!currency && !!sellerCompanyId;

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="max-w-none top-0 left-0 translate-x-0 translate-y-0 h-[100dvh] w-full rounded-none sm:top-1/2 sm:left-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 sm:h-auto sm:w-full sm:max-w-md sm:rounded-xl">
        <DialogHeader>
          <DialogTitle>Новое КП по прайсу</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 overflow-y-auto flex-1 sm:overflow-y-visible">
          {/* Customer typeahead */}
          <div className="space-y-1.5" ref={dropdownRef}>
            <Label>Клиент</Label>
            <div className="relative">
              <Input
                value={customerQuery}
                onChange={(e) => handleCustomerSearch(e.target.value)}
                onFocus={() => {
                  if (customerResults.length > 0 && !selectedCustomer) {
                    setShowDropdown(true);
                  }
                }}
                placeholder="Введите название клиента..."
              />
              {searchingCustomers && (
                <Loader2
                  size={14}
                  className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-text-subtle"
                />
              )}
              {showDropdown && (
                <div className="absolute z-50 mt-1 w-full rounded-md border border-border-light bg-background shadow-md max-h-48 overflow-y-auto">
                  {customerResults.map((customer) => (
                    <button
                      key={customer.id}
                      type="button"
                      className="w-full px-3 py-2 text-left text-sm hover:bg-accent-subtle transition-colors"
                      onClick={() => handleSelectCustomer(customer)}
                    >
                      <div className="font-medium">{customer.name}</div>
                      {customer.inn && (
                        <div className="text-text-muted text-xs">
                          ИНН: {customer.inn}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Currency */}
          <div className="space-y-1.5">
            <Label>Валюта</Label>
            <Select value={currency} onValueChange={(val) => setCurrency(val ?? "USD")}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Выберите валюту" />
              </SelectTrigger>
              <SelectContent>
                {CURRENCIES.map((c) => (
                  <SelectItem key={c.value} value={c.value}>
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Seller company */}
          <div className="space-y-1.5">
            <Label>Наше юрлицо</Label>
            <Select value={sellerCompanyId} onValueChange={(val) => setSellerCompanyId(val ?? "")}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Выберите юрлицо" />
              </SelectTrigger>
              <SelectContent>
                {sellerCompanies.map((company) => (
                  <SelectItem key={company.id} value={company.id}>
                    {company.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Payment terms row */}
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label>Аванс %</Label>
              <Input
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={advancePct}
                onChange={(e) => setAdvancePct(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Отсрочка дней</Label>
              <Input
                type="number"
                min={0}
                max={365}
                step={1}
                value={paymentDays}
                onChange={(e) => setPaymentDays(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Наценка %</Label>
              <Input
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={markupPct}
                onChange={(e) => setMarkupPct(e.target.value)}
              />
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
              type="submit"
              disabled={!isValid || submitting}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Создать
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
