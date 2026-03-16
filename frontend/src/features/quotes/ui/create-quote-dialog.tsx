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
import {
  createQuote,
  searchCustomers,
  fetchSellerCompanies,
} from "@/entities/quote";

const DELIVERY_METHODS = [
  { value: "air", label: "Авиа" },
  { value: "auto", label: "Авто" },
  { value: "sea", label: "Море" },
  { value: "multimodal", label: "Мультимодально" },
] as const;

interface CreateQuoteDialogProps {
  orgId: string;
  userId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateQuoteDialog({
  orgId,
  userId,
  open,
  onOpenChange,
}: CreateQuoteDialogProps) {
  const router = useRouter();

  // Customer typeahead
  const [customerQuery, setCustomerQuery] = useState("");
  const [customerResults, setCustomerResults] = useState<
    Array<{ id: string; name: string; inn: string | null }>
  >([]);
  const [selectedCustomer, setSelectedCustomer] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchingCustomers, setSearchingCustomers] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Seller companies
  const [sellerCompanies, setSellerCompanies] = useState<
    Array<{ id: string; name: string }>
  >([]);
  const [sellerCompanyId, setSellerCompanyId] = useState("");

  // Delivery fields
  const [deliveryCountry, setDeliveryCountry] = useState("Россия");
  const [deliveryCity, setDeliveryCity] = useState("Москва");
  const [deliveryMethod, setDeliveryMethod] = useState("");

  // Submit
  const [submitting, setSubmitting] = useState(false);

  // Load seller companies on open
  useEffect(() => {
    if (!open) return;

    setSelectedCustomer(null);
    setCustomerQuery("");
    setCustomerResults([]);
    setSellerCompanyId("");
    setDeliveryCountry("Россия");
    setDeliveryCity("Москва");
    setDeliveryMethod("");

    fetchSellerCompanies(orgId).then((companies) => {
      setSellerCompanies(companies);
      if (companies.length === 1) {
        setSellerCompanyId(companies[0].id);
      }
    });
  }, [open, orgId]);

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

  function handleSelectCustomer(customer: { id: string; name: string }) {
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

    setSubmitting(true);
    try {
      const result = await createQuote(orgId, userId, {
        customer_id: selectedCustomer.id,
        seller_company_id: sellerCompanyId || undefined,
        delivery_country: deliveryCountry.trim() || undefined,
        delivery_city: deliveryCity.trim() || undefined,
        delivery_method: deliveryMethod || undefined,
      });

      onOpenChange(false);
      router.push(`/quotes/${result.id}`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка создания КП";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Новое КП</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Customer typeahead */}
          <div className="flex flex-col gap-1.5" ref={dropdownRef}>
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Клиент <span className="text-error">*</span>
            </Label>
            <div className="relative">
              <Input
                value={customerQuery}
                onChange={(e) => handleCustomerSearch(e.target.value)}
                onFocus={() => {
                  if (customerResults.length > 0 && !selectedCustomer) {
                    setShowDropdown(true);
                  }
                }}
                placeholder="Введите название или ИНН..."
                autoFocus
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

          {/* Seller company */}
          {sellerCompanies.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Наше юрлицо
              </Label>
              <Select
                value={sellerCompanyId}
                onValueChange={(val) => setSellerCompanyId(val ?? "")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="-- Не указано --" />
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
          )}

          {/* Delivery section */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Страна доставки
              </Label>
              <Input
                value={deliveryCountry}
                onChange={(e) => setDeliveryCountry(e.target.value)}
                placeholder="Россия"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Город доставки
              </Label>
              <Input
                value={deliveryCity}
                onChange={(e) => setDeliveryCity(e.target.value)}
                placeholder="Москва"
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Способ доставки
            </Label>
            <Select value={deliveryMethod} onValueChange={(val) => setDeliveryMethod(val ?? "")}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="-- Не указан --" />
              </SelectTrigger>
              <SelectContent>
                {DELIVERY_METHODS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
              disabled={!selectedCustomer || submitting}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Создать КП
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
