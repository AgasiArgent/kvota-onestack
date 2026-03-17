"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Users, MapPin, Star, Phone, Plus, Pencil, Save, X, Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Customer, CustomerContact, CustomerCall } from "@/entities/customer";
import { updateCustomerAddresses } from "@/entities/customer/mutations";
import { createClient } from "@/shared/lib/supabase/client";
import { ContactFormModal } from "./contact-form-modal";
import { CallFormModal } from "./call-form-modal";

interface Props {
  customer: Customer;
  contacts: CustomerContact[];
  calls: CustomerCall[];
  orgUsers?: { id: string; full_name: string }[];
  currentUserId?: string;
}

export function TabCRM({ customer, contacts, calls, orgUsers, currentUserId }: Props) {
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
      <CallsSection
        calls={calls}
        onAdd={() => setCallModalOpen(true)}
      />
      <Separator />
      <ContactsSection
        contacts={contacts}
        onAdd={openNewContact}
        onEdit={openEditContact}
      />
      <Separator />
      <AddressesSection customer={customer} />

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
        orgUsers={orgUsers}
        currentUserId={currentUserId}
      />
    </div>
  );
}

// -- Contacts Section (4.2: show phones from phones array) --

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
                  <ContactPhoneCell phones={c.phones} legacyPhone={c.phone} />
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

function ContactPhoneCell({
  phones,
  legacyPhone,
}: {
  phones: CustomerContact["phones"];
  legacyPhone: string | null;
}) {
  const primaryPhone = phones?.[0]?.number ?? legacyPhone;
  const extraCount = phones ? phones.length - 1 : 0;

  if (!primaryPhone) return <span className="text-text-muted">—</span>;

  return (
    <span className="inline-flex items-center gap-1">
      <a href={`tel:${primaryPhone}`} className="text-accent hover:underline">
        {primaryPhone}
      </a>
      {extraCount > 0 && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>
              <Badge variant="secondary" className="text-[10px] px-1 py-0 cursor-default">
                +{extraCount}
              </Badge>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs">
              {phones!.slice(1).map((p, i) => (
                <div key={i}>
                  {p.number}{p.ext ? ` доб. ${p.ext}` : ""}{p.label ? ` (${p.label})` : ""}
                </div>
              ))}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </span>
  );
}

// -- Addresses Section (4.5: editable addresses) --

function AddressesSection({ customer }: { customer: Customer }) {
  const router = useRouter();

  const addressFields = [
    { key: "legal_address" as const, label: "Юридический" },
    { key: "actual_address" as const, label: "Фактический" },
    { key: "postal_address" as const, label: "Почтовый" },
  ];

  const [editingAddress, setEditingAddress] = useState<string | null>(null);
  const [editValues, setEditValues] = useState({
    legal_address: customer.legal_address ?? "",
    actual_address: customer.actual_address ?? "",
    postal_address: customer.postal_address ?? "",
  });
  const [editingWarehouses, setEditingWarehouses] = useState(false);
  const [warehouses, setWarehouses] = useState(
    customer.warehouse_addresses ?? []
  );
  const [saving, setSaving] = useState(false);

  const hasAnyAddress = addressFields.some((a) => customer[a.key]);
  const hasWarehouses = customer.warehouse_addresses && customer.warehouse_addresses.length > 0;

  async function saveAddress(key: "legal_address" | "actual_address" | "postal_address") {
    setSaving(true);
    try {
      await updateCustomerAddresses(customer.id, {
        [key]: editValues[key] || undefined,
      });
      setEditingAddress(null);
      router.refresh();
    } catch (err) {
      console.error("Failed to save address:", err);
    } finally {
      setSaving(false);
    }
  }

  function cancelEditAddress(key: "legal_address" | "actual_address" | "postal_address") {
    setEditValues((prev) => ({
      ...prev,
      [key]: customer[key] ?? "",
    }));
    setEditingAddress(null);
  }

  async function saveWarehouses() {
    setSaving(true);
    try {
      const supabase = createClient();
      const filtered = warehouses.filter((w) => w.address.trim() !== "");
      const { error } = await supabase
        .from("customers")
        .update({ warehouse_addresses: filtered.length > 0 ? filtered : null })
        .eq("id", customer.id);
      if (error) throw error;
      setEditingWarehouses(false);
      router.refresh();
    } catch (err) {
      console.error("Failed to save warehouses:", err);
    } finally {
      setSaving(false);
    }
  }

  function cancelEditWarehouses() {
    setWarehouses(customer.warehouse_addresses ?? []);
    setEditingWarehouses(false);
  }

  function addWarehouse() {
    setWarehouses((prev) => [...prev, { address: "", label: "" }]);
  }

  function removeWarehouse(index: number) {
    setWarehouses((prev) => prev.filter((_, i) => i !== index));
  }

  function updateWarehouse(index: number, field: "address" | "label", value: string) {
    setWarehouses((prev) =>
      prev.map((w, i) => (i === index ? { ...w, [field]: value } : w))
    );
  }

  return (
    <div>
      <h3 className="text-base font-semibold mb-3">Адреса</h3>
      {!hasAnyAddress && !hasWarehouses && editingAddress === null && !editingWarehouses ? (
        <div className="py-12 text-center">
          <MapPin size={40} className="mx-auto text-text-subtle mb-3" />
          <p className="text-text-muted mb-1">Нет адресов</p>
          <p className="text-xs text-text-subtle">Адреса клиента появятся здесь</p>
          <Button
            size="sm"
            variant="outline"
            className="mt-3"
            onClick={() => setEditingAddress("legal_address")}
          >
            <Plus size={14} />
            Добавить адрес
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Официальные адреса</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {addressFields.map((addr) => (
                <div key={addr.key}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-xs font-semibold text-text-subtle uppercase">
                      {addr.label}
                    </div>
                    {editingAddress !== addr.key && (
                      <button
                        onClick={() => setEditingAddress(addr.key)}
                        className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-text-muted"
                        title="Редактировать"
                      >
                        <Pencil size={12} />
                      </button>
                    )}
                  </div>
                  {editingAddress === addr.key ? (
                    <div className="space-y-2">
                      <Input
                        value={editValues[addr.key]}
                        onChange={(e) =>
                          setEditValues((prev) => ({
                            ...prev,
                            [addr.key]: e.target.value,
                          }))
                        }
                        placeholder={`${addr.label} адрес`}
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => saveAddress(addr.key)}
                          disabled={saving}
                          className="bg-accent text-white hover:bg-accent-hover"
                        >
                          <Save size={12} />
                          {saving ? "..." : "Сохранить"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => cancelEditAddress(addr.key)}
                          disabled={saving}
                        >
                          <X size={12} />
                          Отмена
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm">{customer[addr.key] || "Не указан"}</div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-base">Склады</CardTitle>
              {!editingWarehouses && (
                <button
                  onClick={() => setEditingWarehouses(true)}
                  className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-text-muted"
                  title="Редактировать"
                >
                  <Pencil size={14} />
                </button>
              )}
            </CardHeader>
            <CardContent>
              {editingWarehouses ? (
                <div className="space-y-3">
                  {warehouses.map((wh, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <Input
                        value={wh.label ?? ""}
                        onChange={(e) => updateWarehouse(i, "label", e.target.value)}
                        placeholder="Название"
                        className="w-32"
                      />
                      <Input
                        value={wh.address}
                        onChange={(e) => updateWarehouse(i, "address", e.target.value)}
                        placeholder="Адрес склада"
                        className="flex-1"
                      />
                      <button
                        onClick={() => removeWarehouse(i)}
                        className="p-2 rounded hover:bg-sidebar text-text-subtle hover:text-error"
                        title="Удалить"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={addWarehouse}
                    className="text-accent"
                  >
                    <Plus size={14} />
                    Добавить склад
                  </Button>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={saveWarehouses}
                      disabled={saving}
                      className="bg-accent text-white hover:bg-accent-hover"
                    >
                      <Save size={12} />
                      {saving ? "..." : "Сохранить"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={cancelEditWarehouses}
                      disabled={saving}
                    >
                      <X size={12} />
                      Отмена
                    </Button>
                  </div>
                </div>
              ) : hasWarehouses ? (
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

// -- Calls Section (4.4: show contact phone, assigned user) --

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
              <TableHead>Телефон</TableHead>
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
                  {call.contact_phone ? (
                    <a href={`tel:${call.contact_phone}`} className="text-accent hover:underline">
                      {call.contact_phone}
                    </a>
                  ) : "—"}
                </TableCell>
                <TableCell className="text-text-muted">
                  <ManagerCell
                    userName={call.user_name}
                    assignedUserName={call.assigned_user_name}
                  />
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

function ManagerCell({
  userName,
  assignedUserName,
}: {
  userName: string | null;
  assignedUserName?: string;
}) {
  if (!userName && !assignedUserName) return <span>—</span>;

  const creator = userName ?? "—";
  if (!assignedUserName || assignedUserName === userName) {
    return <span>{creator}</span>;
  }

  return (
    <span>
      {creator}
      <span className="text-text-subtle">{" "}→ {assignedUserName}</span>
    </span>
  );
}
