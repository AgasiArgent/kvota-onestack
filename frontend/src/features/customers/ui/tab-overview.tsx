"use client";

import { useState } from "react";
import Link from "next/link";
import { Pencil, Save, X, StickyNote } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Customer, CustomerStats } from "@/entities/customer";
import { updateCustomerNotes, updateCustomerGeneralEmail } from "@/entities/customer/mutations";

interface Props {
  customer: Customer;
  stats: CustomerStats;
}

export function TabOverview({ customer, stats }: Props) {
  return (
    <div className="space-y-6">
      {/* Row 1: Requisites + Debt */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Реквизиты</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="ИНН" value={customer.inn} />
            <Row label="КПП" value={customer.kpp} />
            <Row label="ОГРН" value={customer.ogrn} />
            <Row label="Источник" value={customer.order_source} />
            <Row label="Менеджер" value={customer.manager?.full_name} />
            <GeneralEmailField customerId={customer.id} email={customer.general_email} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Задолженность</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Долг" value={`${stats.total_debt.toLocaleString("ru-RU")} ₽`} />
            <Row label="Просрочено" value={`${stats.overdue_count} позиций`} />
            <Row
              label="Последний платёж"
              value={
                stats.last_payment_date
                  ? new Date(stats.last_payment_date).toLocaleDateString("ru-RU")
                  : "нет данных"
              }
            />
          </CardContent>
        </Card>
      </div>

      {/* Row 2: KP + Specs counters */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <CardTitle className="text-base">Коммерческие предложения</CardTitle>
            <Link
              href="?tab=documents&subtab=quotes"
              className="text-sm text-accent hover:underline"
            >
              Все →
            </Link>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <CounterBlock label="На рассмотрении" value={stats.quotes_in_review} />
              <CounterBlock label="В подготовке" value={stats.quotes_in_progress} />
              <CounterBlock label="Всего" value={stats.quotes_total} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <CardTitle className="text-base">Спецификации</CardTitle>
            <Link
              href="?tab=documents&subtab=specs"
              className="text-sm text-accent hover:underline"
            >
              Все →
            </Link>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <CounterBlock label="Активных" value={stats.specs_active} />
              <CounterBlock label="Подписанных" value={stats.specs_signed} />
              <CounterBlock label="Всего" value={stats.specs_total} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 3: Notes */}
      <NotesSection customerId={customer.id} notes={customer.notes} />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-muted">{label}</span>
      <span className="font-medium">{value ?? "—"}</span>
    </div>
  );
}

function CounterBlock({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-xs text-text-muted mt-1">{label}</div>
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
            placeholder="Добавить заметки о клиенте"
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
          <p className="text-xs text-text-subtle">Добавить заметки о клиенте</p>
        </div>
      )}
    </div>
  );
}

function GeneralEmailField({ customerId, email: initialEmail }: { customerId: string; email: string | null }) {
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState(initialEmail ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await updateCustomerGeneralEmail(customerId, email);
      setEditing(false);
    } catch (err) {
      console.error("Failed to save email:", err);
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setEmail(initialEmail ?? "");
    setEditing(false);
  }

  if (editing) {
    return (
      <div className="flex justify-between items-start">
        <span className="text-text-muted pt-1">Email</span>
        <div className="flex items-center gap-1">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="px-2 py-1 text-sm border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent w-48"
            placeholder="Добавить email"
          />
          <button
            onClick={handleSave}
            disabled={saving}
            className="p-1 rounded hover:bg-sidebar text-accent"
            title="Сохранить"
          >
            <Save size={14} />
          </button>
          <button
            onClick={handleCancel}
            disabled={saving}
            className="p-1 rounded hover:bg-sidebar text-text-subtle"
            title="Отмена"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-between">
      <span className="text-text-muted">Email</span>
      <button
        onClick={() => setEditing(true)}
        className="font-medium text-right hover:text-accent transition-colors"
        title="Редактировать email"
      >
        {initialEmail ? (
          <a href={`mailto:${initialEmail}`} className="text-accent hover:underline" onClick={(e) => e.stopPropagation()}>
            {initialEmail}
          </a>
        ) : (
          <span className="text-text-subtle">Добавить email</span>
        )}
      </button>
    </div>
  );
}
