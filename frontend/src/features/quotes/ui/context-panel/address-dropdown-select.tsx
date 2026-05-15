"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, X, Plus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { createClient } from "@/shared/lib/supabase/client";
import { patchQuote } from "@/entities/quote/mutations";
import { AddAddressForm } from "./add-address-form";

interface DeliveryAddress {
  id: string;
  name: string | null;
  address: string;
  is_default: boolean;
}

interface WarehouseAddressEntry {
  address?: string | null;
  label?: string | null;
}

interface AddressDropdownSelectProps {
  quoteId: string;
  customerId: string;
  initialAddress: string | null;
}

export function AddressDropdownSelect({
  quoteId,
  customerId,
  initialAddress,
}: AddressDropdownSelectProps) {
  const [open, setOpen] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [search, setSearch] = useState("");
  const [addresses, setAddresses] = useState<DeliveryAddress[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentAddress, setCurrentAddress] = useState(initialAddress);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setShowAddForm(false);
        setSearch("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function fetchAddresses() {
    if (addresses !== null) return;
    setLoading(true);

    // Testing 2 row 24 (FB 2026-05-14): the delivery-address dropdown lists
    // only warehouses (склады). It merges two warehouse sources — explicit
    // rows in `customer_delivery_addresses` and the customer's
    // `warehouse_addresses` jsonb array — deduping by trimmed/lowercased
    // address string so a warehouse present in both shows up once. The
    // customer's legal/actual/postal address text fields are intentionally
    // NOT listed: the tester wants warehouses only.
    try {
      const supabase = createClient();
      const [deliveryRes, customerRes] = await Promise.all([
        supabase
          .from("customer_delivery_addresses")
          .select("id, name, address, is_default")
          .eq("customer_id", customerId)
          .order("is_default", { ascending: false })
          .order("name"),
        supabase
          .from("customers")
          .select("warehouse_addresses")
          .eq("id", customerId)
          .maybeSingle(),
      ]);

      if (deliveryRes.error) throw deliveryRes.error;
      if (customerRes.error) throw customerRes.error;

      const merged: DeliveryAddress[] = [];
      const seen = new Set<string>();

      function pushIfFresh(entry: DeliveryAddress) {
        const key = entry.address.trim().toLowerCase();
        if (!key || seen.has(key)) return;
        seen.add(key);
        merged.push(entry);
      }

      // 1. Rows from customer_delivery_addresses keep their original name.
      for (const row of deliveryRes.data ?? []) {
        if (!row.address) continue;
        pushIfFresh({
          id: row.id,
          name: row.name ?? null,
          address: row.address,
          is_default: row.is_default ?? false,
        });
      }

      const customer = customerRes.data ?? null;
      const customerRecord = customer as Record<string, unknown> | null;

      // 2. warehouse_addresses jsonb array → "Склад: <label or address>".
      const rawWarehouses = customerRecord?.warehouse_addresses;
      const warehouses: WarehouseAddressEntry[] = Array.isArray(rawWarehouses)
        ? (rawWarehouses as WarehouseAddressEntry[])
        : [];
      warehouses.forEach((wh, idx) => {
        const address = (wh?.address ?? "").trim();
        if (!address) return;
        const label = (wh?.label ?? "").trim();
        pushIfFresh({
          id: `customer-warehouse-${idx}`,
          name: `Склад: ${label || address}`,
          address,
          is_default: false,
        });
      });

      setAddresses(merged);
    } catch {
      toast.error("Не удалось загрузить адреса");
    } finally {
      setLoading(false);
    }
  }

  function handleTriggerClick() {
    setOpen(true);
    setShowAddForm(false);
    fetchAddresses();
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  async function handleSelect(address: string) {
    const prev = currentAddress;
    setCurrentAddress(address);
    setOpen(false);
    setShowAddForm(false);
    setSearch("");

    try {
      await patchQuote(quoteId, { delivery_address: address });
    } catch {
      setCurrentAddress(prev);
      toast.error("Не удалось сохранить");
    }
  }

  async function handleClear(e: React.MouseEvent) {
    e.stopPropagation();
    const prev = currentAddress;
    setCurrentAddress(null);
    setSearch("");

    try {
      await patchQuote(quoteId, { delivery_address: null });
    } catch {
      setCurrentAddress(prev);
      toast.error("Не удалось сохранить");
    }
  }

  async function handleAddCreated(created: { id: string; address: string }) {
    setAddresses((prev) => [
      ...(prev ?? []),
      { id: created.id, name: null, address: created.address, is_default: false },
    ]);
    setShowAddForm(false);
    await handleSelect(created.address);
  }

  const filtered = addresses
    ? search
      ? addresses.filter(
          (a) =>
            a.address.toLowerCase().includes(search.toLowerCase()) ||
            (a.name ?? "").toLowerCase().includes(search.toLowerCase())
        )
      : addresses
    : [];

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger */}
      <button
        type="button"
        onClick={handleTriggerClick}
        className="flex items-start gap-1 text-sm font-medium hover:text-accent transition-colors max-w-full text-left"
      >
        {/*
          Testing 2 row 1 (FB-260513-100622-47b6): tester expects to see the
          full delivery address \u2014 `truncate` clipped it to a single line on
          the info panel grid. `line-clamp-2` lets long addresses wrap to a
          second line while still preventing the panel from growing unbounded.
        */}
        <span className="line-clamp-2 break-words">
          {currentAddress ?? "\u2014"}
        </span>
        {currentAddress ? (
          <X
            size={12}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            onClick={handleClear}
          />
        ) : (
          <ChevronDown size={12} className="shrink-0 text-muted-foreground" />
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute top-full left-0 z-[300] mt-1 min-w-[260px] rounded-lg border bg-popover shadow-md">
          {showAddForm ? (
            <AddAddressForm
              customerId={customerId}
              onCreated={handleAddCreated}
              onCancel={() => setShowAddForm(false)}
            />
          ) : (
            <>
              <div className="p-1.5">
                <input
                  ref={inputRef}
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Поиск..."
                  className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none focus:border-ring"
                />
              </div>
              <div className="max-h-[200px] overflow-y-auto p-1">
                {loading ? (
                  <div className="flex items-center justify-center py-3">
                    <Loader2 size={16} className="animate-spin text-muted-foreground" />
                  </div>
                ) : filtered.length === 0 ? (
                  <div className="py-2 px-2 text-sm text-muted-foreground text-center">
                    Нет адресов
                  </div>
                ) : (
                  filtered.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => handleSelect(a.address)}
                      className={cn(
                        "flex w-full flex-col items-start rounded-md px-2 py-1.5 text-sm cursor-default",
                        "hover:bg-accent hover:text-accent-foreground",
                        a.address === currentAddress && "bg-accent/10 font-medium"
                      )}
                    >
                      <span className="truncate w-full text-left">
                        {a.address}
                      </span>
                      {a.name && (
                        <span className="text-xs text-muted-foreground truncate w-full text-left">
                          {a.name}
                        </span>
                      )}
                    </button>
                  ))
                )}
              </div>
              <div className="border-t border-border p-1">
                <button
                  type="button"
                  onClick={() => setShowAddForm(true)}
                  className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                >
                  <Plus size={14} />
                  Добавить адрес
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
