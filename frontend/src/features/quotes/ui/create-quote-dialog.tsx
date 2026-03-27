"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus, CheckCircle2 } from "lucide-react";
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
} from "@/entities/quote/mutations";
import { createCustomer } from "@/entities/customer/mutations";

interface DaDataResult {
  found: boolean;
  name?: string;
  kpp?: string | null;
  ogrn?: string | null;
  address?: string | null;
}

function isInnQuery(query: string): boolean {
  const cleaned = query.replace(/\D/g, "");
  return cleaned.length >= 10 && cleaned.length <= 12 && /^\d+$/.test(cleaned);
}

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

  // DaData lookup for new customers
  const [dadataResult, setDadataResult] = useState<DaDataResult | null>(null);
  const [lookingUpDadata, setLookingUpDadata] = useState(false);
  const [creatingCustomer, setCreatingCustomer] = useState(false);

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
    setDadataResult(null);
    setLookingUpDadata(false);
    setCreatingCustomer(false);
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
      setDadataResult(null);

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
          setShowDropdown(true);

          // If no DB results and query looks like INN, look up in DaData
          if (results.length === 0 && isInnQuery(value)) {
            setLookingUpDadata(true);
            try {
              const res = await fetch("/proxy/dadata", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ inn: value.replace(/\D/g, "") }),
              });
              if (res.ok) {
                const data: DaDataResult = await res.json();
                setDadataResult(data);
              }
            } catch {
              // DaData unavailable — not critical
            } finally {
              setLookingUpDadata(false);
            }
          }
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

  async function handleCreateFromDadata() {
    if (!dadataResult?.found || !dadataResult.name) return;

    setCreatingCustomer(true);
    try {
      const innValue = customerQuery.replace(/\D/g, "");
      const newCustomer = await createCustomer(orgId, {
        name: dadataResult.name,
        inn: innValue,
        kpp: dadataResult.kpp ?? undefined,
        ogrn: dadataResult.ogrn ?? undefined,
        legal_address: dadataResult.address ?? undefined,
      });

      handleSelectCustomer({ id: newCustomer.id, name: dadataResult.name });
      toast.success(`Клиент "${dadataResult.name}" создан`);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка создания клиента";
      if (message.includes("duplicate") || message.includes("unique")) {
        toast.error("Клиент с таким ИНН уже существует");
      } else {
        toast.error(message);
      }
    } finally {
      setCreatingCustomer(false);
    }
  }

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
              {(searchingCustomers || lookingUpDadata) && (
                <Loader2
                  size={14}
                  className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-text-subtle"
                />
              )}
              {selectedCustomer && (
                <CheckCircle2
                  size={14}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-green-600"
                />
              )}
              {showDropdown && (
                <div className="absolute z-[300] mt-1 w-full rounded-md border border-border-light bg-background shadow-md max-h-48 overflow-y-auto">
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

                  {customerResults.length === 0 && !lookingUpDadata && !dadataResult && (
                    <div className="px-3 py-3 text-sm text-text-muted">
                      Клиент не найден
                    </div>
                  )}

                  {lookingUpDadata && (
                    <div className="px-3 py-3 text-sm text-text-muted flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin" />
                      Поиск по ИНН в DaData...
                    </div>
                  )}

                  {dadataResult?.found && dadataResult.name && (
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left text-sm hover:bg-green-50 transition-colors border-t border-border-light"
                      onClick={handleCreateFromDadata}
                      disabled={creatingCustomer}
                    >
                      <div className="flex items-center gap-2">
                        {creatingCustomer ? (
                          <Loader2 size={14} className="animate-spin text-green-600" />
                        ) : (
                          <Plus size={14} className="text-green-600" />
                        )}
                        <span className="font-medium text-green-700">
                          Создать: {dadataResult.name}
                        </span>
                      </div>
                      {dadataResult.address && (
                        <div className="text-text-muted text-xs mt-0.5 ml-6">
                          {dadataResult.address}
                        </div>
                      )}
                    </button>
                  )}

                  {dadataResult && !dadataResult.found && (
                    <div className="px-3 py-3 text-sm text-text-muted">
                      <div>ИНН не найден в DaData</div>
                      <div className="text-xs mt-1">
                        Создайте клиента на странице{" "}
                        <a
                          href="/customers"
                          target="_blank"
                          className="underline text-accent hover:text-accent-hover"
                        >
                          Клиенты
                        </a>
                      </div>
                    </div>
                  )}
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
