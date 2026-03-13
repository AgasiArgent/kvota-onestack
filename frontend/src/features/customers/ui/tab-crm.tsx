"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Customer, CustomerContact } from "@/entities/customer";

interface Props {
  customer: Customer;
  contacts: CustomerContact[];
}

type SubTab = "contacts" | "addresses" | "calls" | "meetings" | "notes";

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "contacts", label: "Контакты" },
  { key: "addresses", label: "Адреса" },
  { key: "calls", label: "Звонки" },
  { key: "meetings", label: "Встречи" },
  { key: "notes", label: "Заметки" },
];

export function TabCRM({ customer, contacts }: Props) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("contacts");

  return (
    <div>
      {/* Sub-tab pills */}
      <div className="flex gap-2 mb-6">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSubTab(tab.key)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              activeSubTab === tab.key
                ? "bg-blue-100 text-blue-700 font-medium"
                : "text-slate-500 hover:bg-slate-100"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeSubTab === "contacts" && <ContactsSection contacts={contacts} />}
      {activeSubTab === "addresses" && <AddressesSection customer={customer} />}
      {activeSubTab === "calls" && <PlaceholderSection name="Звонки" />}
      {activeSubTab === "meetings" && <PlaceholderSection name="Встречи" />}
      {activeSubTab === "notes" && <NotesSection notes={customer.notes} />}
    </div>
  );
}

function ContactsSection({ contacts }: { contacts: CustomerContact[] }) {
  if (contacts.length === 0) {
    return <p className="text-slate-400 py-8 text-center">Нет контактов</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ФИО</TableHead>
          <TableHead>Должность</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Телефон</TableHead>
          <TableHead>Заметки</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {contacts.map((c) => (
          <TableRow key={c.id}>
            <TableCell className="font-medium">
              {c.name}
              {c.is_primary && <span className="ml-1 text-yellow-500" title="Основной">★</span>}
              {c.is_lpr && <span className="ml-1 text-blue-500 text-xs">ЛПР</span>}
            </TableCell>
            <TableCell className="text-slate-500">{c.position ?? "—"}</TableCell>
            <TableCell>
              {c.email ? (
                <a href={`mailto:${c.email}`} className="text-blue-600 hover:underline">
                  {c.email}
                </a>
              ) : "—"}
            </TableCell>
            <TableCell>
              {c.phone ? (
                <a href={`tel:${c.phone}`} className="text-blue-600 hover:underline">
                  {c.phone}
                </a>
              ) : "—"}
            </TableCell>
            <TableCell className="text-slate-500 max-w-[200px] truncate">
              {c.notes ?? "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function AddressesSection({ customer }: { customer: Customer }) {
  const addresses = [
    { label: "Юридический", value: customer.legal_address },
    { label: "Фактический", value: customer.actual_address },
    { label: "Почтовый", value: customer.postal_address },
  ];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Официальные адреса</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {addresses.map((addr) => (
            <div key={addr.label}>
              <div className="text-xs font-semibold text-slate-400 uppercase">{addr.label}</div>
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
          {customer.warehouse_addresses && customer.warehouse_addresses.length > 0 ? (
            <div className="space-y-2">
              {customer.warehouse_addresses.map((wh, i) => (
                <div key={i} className="text-sm">
                  {wh.label && <span className="font-medium">{wh.label}: </span>}
                  {wh.address}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-400 text-sm">Нет адресов складов</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function NotesSection({ notes }: { notes: string | null }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Заметки / Примечания</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm whitespace-pre-wrap">
          {notes || "Нет заметок"}
        </p>
      </CardContent>
    </Card>
  );
}

function PlaceholderSection({ name }: { name: string }) {
  return (
    <div className="py-8 text-center text-slate-400">
      {name} — в разработке
    </div>
  );
}
