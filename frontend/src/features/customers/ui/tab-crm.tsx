"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Users, MapPin, StickyNote, Star, Phone, Plus, Pencil, Save, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { Customer, CustomerContact, CustomerCall } from "@/entities/customer";
import { updateCustomerNotes } from "@/entities/customer";
import { ContactFormModal } from "./contact-form-modal";
import { CallFormModal } from "./call-form-modal";

interface Props {
  customer: Customer;
  contacts: CustomerContact[];
  calls: CustomerCall[];
}

export function TabCRM({ customer, contacts, calls }: Props) {
  const router = useRouter();
  const [contactModalOpen, setContactModalOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<CustomerContact | undefined>();
  const [callModalOpen, setCallModalOpen] = useState(false);

  function handleContactSaved() {
    router.refresh();
  }

  function handleCallSaved() {
    router.refresh();
  }

  function openEditContact(contact: CustomerContact) {
    setEditingContact(contact);
    setContactModalOpen(true);
  }

  function openNewContact() {
    setEditingContact(undefined);
    setContactModalOpen(true);
  }

  return (
    <div className="space-y-6">
      <ContactsSection
        contacts={contacts}
        onAdd={openNewContact}
        onEdit={openEditContact}
      />
      <Separator />
      <AddressesSection customer={customer} />
      <Separator />
      <CallsSection
        calls={calls}
        onAdd={() => setCallModalOpen(true)}
      />
      <Separator />
      <NotesSection customerId={customer.id} notes={customer.notes} />

      <ContactFormModal
        open={contactModalOpen}
        onClose={() => { setContactModalOpen(false); setEditingContact(undefined); }}
        onSaved={handleContactSaved}
        customerId={customer.id}
        contact={editingContact}
      />
      <CallFormModal
        open={callModalOpen}
        onClose={() => setCallModalOpen(false)}
        onSaved={handleCallSaved}
        customerId={customer.id}
        contacts={contacts}
      />
    </div>
  );
}

function ContactsSection({
  contacts,
  onAdd,
  onEdit,
}: {
  contacts: CustomerContact[];
  onAdd: () => void;
  onEdit: (c: CustomerContact) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Контакты</h3>
        <Button size="sm" variant="outline" onClick={onAdd}>
          <Plus size={14} />
          Добавить
        </Button>
      </div>
      {contacts.length === 0 ? (
        <div className="py-12 text-center">
          <Users size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет контактов</p>
          <p className="text-xs text-text-subtle">Контакты этого клиента появятся здесь</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ФИО</TableHead>
              <TableHead>Должность</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Телефон</TableHead>
              <TableHead>Заметки</TableHead>
              <TableHead className="w-[40px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">
                  {c.name}
                  {c.is_primary && <Star size={14} className="ml-1 text-yellow-500 fill-yellow-500 inline" />}
                  {c.is_lpr && <span className="ml-1 text-accent text-xs">ЛПР</span>}
                </TableCell>
                <TableCell className="text-text-muted">{c.position ?? "—"}</TableCell>
                <TableCell>
                  {c.email ? (
                    <a href={`mailto:${c.email}`} className="text-accent hover:underline">
                      {c.email}
                    </a>
                  ) : "—"}
                </TableCell>
                <TableCell>
                  {c.phone ? (
                    <a href={`tel:${c.phone}`} className="text-accent hover:underline">
                      {c.phone}
                    </a>
                  ) : "—"}
                </TableCell>
                <TableCell className="text-text-muted max-w-[200px] truncate">
                  {c.notes ?? "—"}
                </TableCell>
                <TableCell>
                  <button
                    onClick={() => onEdit(c)}
                    className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-text-muted"
                    title="Редактировать"
                  >
                    <Pencil size={14} />
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function AddressesSection({ customer }: { customer: Customer }) {
  const addresses = [
    { label: "Юридический", value: customer.legal_address },
    { label: "Фактический", value: customer.actual_address },
    { label: "Почтовый", value: customer.postal_address },
  ];

  const hasAnyAddress = addresses.some((a) => a.value);
  const hasWarehouses = customer.warehouse_addresses && customer.warehouse_addresses.length > 0;

  return (
    <div>
      <h3 className="text-base font-semibold mb-3">Адреса</h3>
      {!hasAnyAddress && !hasWarehouses ? (
        <div className="py-12 text-center">
          <MapPin size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет адресов</p>
          <p className="text-xs text-text-subtle">Адреса клиента появятся здесь</p>
        </div>
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Официальные адреса</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {addresses.map((addr) => (
                <div key={addr.label}>
                  <div className="text-xs font-semibold text-text-subtle uppercase">{addr.label}</div>
                  <div className="text-sm">{addr.value || "Не указан"}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Склады</CardTitle>
            </CardHeader>
            <CardContent>
              {hasWarehouses ? (
                <div className="space-y-2">
                  {customer.warehouse_addresses!.map((wh, i) => (
                    <div key={i} className="text-sm">
                      {wh.label && <span className="font-medium">{wh.label}: </span>}
                      {wh.address}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-text-subtle text-sm">Нет адресов складов</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

const CALL_TYPE_LABELS: Record<string, string> = {
  call: "Звонок",
  scheduled: "Встреча",
};

const CALL_CATEGORY_LABELS: Record<string, string> = {
  cold: "Холодный",
  warm: "Тёплый",
  incoming: "Входящий",
};

function CallsSection({
  calls,
  onAdd,
}: {
  calls: CustomerCall[];
  onAdd: () => void;
}) {
  function formatDate(d: string | null) {
    if (!d) return "—";
    return new Date(d).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Звонки и встречи</h3>
        <Button size="sm" variant="outline" onClick={onAdd}>
          <Plus size={14} />
          Добавить
        </Button>
      </div>
      {calls.length === 0 ? (
        <div className="py-12 text-center">
          <Phone size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет звонков и встреч</p>
          <p className="text-xs text-text-subtle">История взаимодействий с клиентом появится здесь</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Дата</TableHead>
              <TableHead>Тип</TableHead>
              <TableHead>Категория</TableHead>
              <TableHead>Контакт</TableHead>
              <TableHead>Менеджер</TableHead>
              <TableHead>Комментарий</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {calls.map((call) => (
              <TableRow key={call.id}>
                <TableCell className="text-text-muted tabular-nums whitespace-nowrap">
                  {call.call_type === "scheduled" && call.scheduled_date
                    ? formatDate(call.scheduled_date)
                    : formatDate(call.created_at)}
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">
                    {CALL_TYPE_LABELS[call.call_type] ?? call.call_type}
                  </Badge>
                </TableCell>
                <TableCell className="text-text-muted">
                  {call.call_category
                    ? CALL_CATEGORY_LABELS[call.call_category] ?? call.call_category
                    : "—"}
                </TableCell>
                <TableCell className="text-text-muted">
                  {call.contact_name ?? "—"}
                </TableCell>
                <TableCell className="text-text-muted">
                  {call.user_name ?? "—"}
                </TableCell>
                <TableCell className="text-text-muted max-w-[250px] truncate">
                  {call.comment ?? call.meeting_notes ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function NotesSection({ customerId, notes: initialNotes }: { customerId: string; notes: string | null }) {
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(initialNotes ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await updateCustomerNotes(customerId, notes);
      setEditing(false);
    } catch (err) {
      console.error("Failed to save notes:", err);
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setNotes(initialNotes ?? "");
    setEditing(false);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold">Заметки</h3>
        {!editing && (
          <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
            <Pencil size={14} />
            Редактировать
          </Button>
        )}
      </div>
      {editing ? (
        <div className="space-y-3">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={5}
            className="w-full px-3 py-2 text-sm border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent resize-y"
            placeholder="Заметки о клиенте..."
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              <Save size={14} />
              {saving ? "Сохранение..." : "Сохранить"}
            </Button>
            <Button size="sm" variant="outline" onClick={handleCancel} disabled={saving}>
              <X size={14} />
              Отмена
            </Button>
          </div>
        </div>
      ) : notes ? (
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm whitespace-pre-wrap">{notes}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="py-12 text-center">
          <StickyNote size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет заметок</p>
          <p className="text-xs text-text-subtle">Заметки и примечания появятся здесь</p>
        </div>
      )}
    </div>
  );
}
