"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { CustomerContact } from "@/entities/customer";
import { createClient } from "@/shared/lib/supabase/client";

// ── Types ───────────────────────────────────────────────────────────

type CallType = "call" | "scheduled";
type CallCategory = "cold" | "warm" | "incoming";

interface CallFormData {
  call_type: CallType;
  call_category: CallCategory | null;
  contact_person_id: string | null;
  scheduled_date: string | null;
  comment: string;
  customer_needs: string;
  meeting_notes: string;
}

interface CallFormModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  customerId: string;
  contacts: CustomerContact[];
}

// ── Inline mutation (until entities/customer/mutations is ready) ─────

async function createCall(customerId: string, data: CallFormData) {
  const supabase = createClient();

  const { data: customer } = await supabase
    .from("customers")
    .select("organization_id")
    .eq("id", customerId)
    .single();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!customer?.organization_id || !user?.id) {
    throw new Error("Не удалось определить организацию или пользователя");
  }

  const { error } = await supabase.from("calls").insert({
    customer_id: customerId,
    organization_id: customer.organization_id,
    user_id: user.id,
    call_type: data.call_type,
    call_category: data.call_category,
    contact_person_id: data.contact_person_id,
    scheduled_date: data.scheduled_date,
    comment: data.comment || null,
    customer_needs: data.customer_needs || null,
    meeting_notes: data.meeting_notes || null,
  });

  if (error) throw error;
}

// ── Constants ───────────────────────────────────────────────────────

const CALL_CATEGORIES: { value: CallCategory; label: string }[] = [
  { value: "cold", label: "Холодный" },
  { value: "warm", label: "Тёплый" },
  { value: "incoming", label: "Входящий" },
];

const INITIAL_FORM: CallFormData = {
  call_type: "call",
  call_category: null,
  contact_person_id: null,
  scheduled_date: null,
  comment: "",
  customer_needs: "",
  meeting_notes: "",
};

// ── Component ───────────────────────────────────────────────────────

export function CallFormModal({
  open,
  onClose,
  onSaved,
  customerId,
  contacts,
}: CallFormModalProps) {
  const [form, setForm] = useState<CallFormData>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsExpanded, setNeedsExpanded] = useState(false);

  const isScheduled = form.call_type === "scheduled";
  const title = isScheduled ? "Новая встреча" : "Новый звонок";

  function resetAndClose() {
    setForm(INITIAL_FORM);
    setError(null);
    setNeedsExpanded(false);
    onClose();
  }

  function handleOpenChange(open: boolean) {
    if (!open) resetAndClose();
  }

  function updateField<K extends keyof CallFormData>(
    key: K,
    value: CallFormData[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const payload: CallFormData = {
        ...form,
        call_category: form.call_category || null,
        contact_person_id: form.contact_person_id || null,
        scheduled_date: form.scheduled_date || null,
        comment: form.comment.trim(),
        customer_needs: form.customer_needs.trim() || "",
        meeting_notes: form.meeting_notes.trim() || "",
      };
      await createCall(customerId, payload);
      setForm(INITIAL_FORM);
      setNeedsExpanded(false);
      onSaved();
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Не удалось сохранить запись",
      );
    } finally {
      setSaving(false);
    }
  }

  function getContactLabel(contact: CustomerContact): string {
    const parts = [contact.name, contact.last_name].filter(Boolean);
    if (contact.position) parts.push(`(${contact.position})`);
    return parts.join(" ");
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Call type pills */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Тип
            </label>
            <div className="flex gap-2">
              <TypePill
                active={form.call_type === "call"}
                onClick={() => updateField("call_type", "call")}
              >
                Звонок
              </TypePill>
              <TypePill
                active={form.call_type === "scheduled"}
                onClick={() => updateField("call_type", "scheduled")}
              >
                Встреча
              </TypePill>
            </div>
          </div>

          {/* Category */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Категория
            </label>
            <Select
              value={form.call_category ?? undefined}
              onValueChange={(val) =>
                updateField("call_category", (val as CallCategory) || null)
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Не выбрана" />
              </SelectTrigger>
              <SelectContent>
                {CALL_CATEGORIES.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value}>
                    {cat.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Contact person */}
          {contacts.length > 0 && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Контактное лицо
              </label>
              <Select
                value={form.contact_person_id ?? undefined}
                onValueChange={(val) =>
                  updateField("contact_person_id", val || null)
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Не выбрано" />
                </SelectTrigger>
                <SelectContent>
                  {contacts.map((contact) => (
                    <SelectItem key={contact.id} value={contact.id}>
                      {getContactLabel(contact)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Scheduled date — only for meetings */}
          {isScheduled && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Дата и время
              </Label>
              <Input
                type="datetime-local"
                value={form.scheduled_date ?? ""}
                onChange={(e) =>
                  updateField("scheduled_date", e.target.value || null)
                }
              />
            </div>
          )}

          {/* Comment */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Комментарий
            </label>
            <Textarea
              value={form.comment}
              onChange={(e) => updateField("comment", e.target.value)}
              placeholder="Краткое описание звонка или встречи..."
              rows={3}
            />
          </div>

          {/* Customer needs — collapsible */}
          <div>
            <button
              type="button"
              onClick={() => setNeedsExpanded((v) => !v)}
              className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-text-muted hover:text-text transition-colors"
            >
              Потребности клиента
              {needsExpanded ? (
                <ChevronUp size={14} />
              ) : (
                <ChevronDown size={14} />
              )}
            </button>
            {needsExpanded && (
              <Textarea
                className="mt-1.5"
                value={form.customer_needs}
                onChange={(e) => updateField("customer_needs", e.target.value)}
                placeholder="Что ищет клиент, какие задачи решает..."
                rows={2}
              />
            )}
          </div>

          {/* Meeting notes — only for meetings */}
          {isScheduled && (
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Заметки о встрече
              </label>
              <Textarea
                value={form.meeting_notes}
                onChange={(e) => updateField("meeting_notes", e.target.value)}
                placeholder="Результаты встречи, договорённости..."
                rows={3}
              />
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-xs text-error">{error}</p>
          )}

          {/* Footer */}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={resetAndClose}
              disabled={saving}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={saving}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {saving && <Loader2 size={16} className="animate-spin" />}
              Сохранить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Type pill sub-component ─────────────────────────────────────────

function TypePill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? "bg-accent-subtle text-accent border-transparent"
          : "border-border text-text-muted hover:bg-sidebar"
      }`}
    >
      {children}
    </button>
  );
}
