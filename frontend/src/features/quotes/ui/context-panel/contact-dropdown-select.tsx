"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, X, Plus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { patchQuote } from "@/entities/quote/mutations";
import { createClient } from "@/shared/lib/supabase/client";
import { AddContactForm } from "./add-contact-form";

interface ContactOption {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
}

interface ContactDropdownSelectProps {
  quoteId: string;
  customerId: string;
  initialContact: { id: string; name: string } | null;
}

export function ContactDropdownSelect({
  quoteId,
  customerId,
  initialContact,
}: ContactDropdownSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [contacts, setContacts] = useState<ContactOption[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<{ id: string; name: string } | null>(
    initialContact
  );
  const [addFormOpen, setAddFormOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setSearch("");
        setAddFormOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function fetchContacts() {
    if (contacts !== null) return;
    setLoading(true);
    try {
      const supabase = createClient();
      const { data, error } = await supabase
        .from("customer_contacts")
        .select("id, name, phone, email")
        .eq("customer_id", customerId)
        .order("is_primary", { ascending: false })
        .order("name");

      if (error) throw error;

      setContacts(
        (data ?? []).map((c) => ({
          id: c.id,
          name: c.name,
          phone: c.phone ?? null,
          email: c.email ?? null,
        }))
      );
    } catch {
      toast.error("Не удалось загрузить контакты");
    } finally {
      setLoading(false);
    }
  }

  function handleTriggerClick() {
    if (!open) {
      setOpen(true);
      fetchContacts();
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setOpen(false);
      setSearch("");
      setAddFormOpen(false);
    }
  }

  async function handleSelect(contact: ContactOption) {
    const prev = selected;
    setSelected({ id: contact.id, name: contact.name });
    setOpen(false);
    setSearch("");
    setAddFormOpen(false);

    try {
      await patchQuote(quoteId, { contact_person_id: contact.id });
    } catch {
      setSelected(prev);
      toast.error("Не удалось сохранить");
    }
  }

  async function handleClear(e: React.MouseEvent) {
    e.stopPropagation();
    const prev = selected;
    setSelected(null);

    try {
      await patchQuote(quoteId, { contact_person_id: null });
    } catch {
      setSelected(prev);
      toast.error("Не удалось сохранить");
    }
  }

  async function handleContactCreated(contact: { id: string; name: string }) {
    const newContact: ContactOption = { id: contact.id, name: contact.name, phone: null, email: null };
    setAddFormOpen(false);
    setContacts((prev) => (prev ? [...prev, newContact] : [newContact]));
    await handleSelect(newContact);
  }

  const filtered =
    contacts?.filter((c) =>
      c.name.toLowerCase().includes(search.toLowerCase())
    ) ?? [];

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger */}
      <button
        type="button"
        onClick={handleTriggerClick}
        className="group flex items-center gap-1 text-sm font-medium hover:text-accent transition-colors"
      >
        <span className="truncate">
          {selected ? selected.name : "\u2014"}
        </span>
        {selected ? (
          <X
            size={12}
            className="shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-foreground transition-opacity"
            onClick={handleClear}
          />
        ) : (
          <ChevronDown
            size={12}
            className="shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
          />
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute top-full left-0 z-[300] mt-1 min-w-[240px] rounded-lg border bg-popover shadow-md">
          {addFormOpen ? (
            <AddContactForm
              customerId={customerId}
              onCreated={handleContactCreated}
              onCancel={() => setAddFormOpen(false)}
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
                  <div className="flex items-center justify-center gap-2 py-3 text-sm text-muted-foreground">
                    <Loader2 size={14} className="animate-spin" />
                    Загрузка...
                  </div>
                ) : filtered.length === 0 ? (
                  <div className="py-2 px-2 text-sm text-muted-foreground text-center">
                    Нет контактов
                  </div>
                ) : (
                  filtered.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => handleSelect(c)}
                      className={cn(
                        "flex w-full flex-col items-start rounded-md px-2 py-1.5 text-sm cursor-default",
                        "hover:bg-accent hover:text-accent-foreground",
                        c.id === selected?.id && "bg-accent/10 font-medium"
                      )}
                    >
                      <span className="truncate">{c.name}</span>
                      {(c.phone || c.email) && (
                        <span className="text-xs text-muted-foreground truncate">
                          {[c.phone, c.email].filter(Boolean).join(" \u00B7 ")}
                        </span>
                      )}
                    </button>
                  ))
                )}
              </div>
              <div className="border-t p-1">
                <button
                  type="button"
                  onClick={() => setAddFormOpen(true)}
                  className="flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-accent hover:bg-accent/10 transition-colors"
                >
                  <Plus size={14} />
                  Добавить контакт
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
