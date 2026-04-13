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

    try {
      const supabase = createClient();
      const { data, error } = await supabase
        .from("customer_delivery_addresses")
        .select("id, name, address, is_default")
        .eq("customer_id", customerId)
        .order("is_default", { ascending: false })
        .order("name");

      if (error) throw error;

      setAddresses(
        (data ?? []).map((row) => ({
          id: row.id,
          name: row.name ?? null,
          address: row.address,
          is_default: row.is_default ?? false,
        }))
      );
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
        className="flex items-center gap-1 text-sm font-medium hover:text-accent transition-colors max-w-full"
      >
        <span className="truncate">
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
