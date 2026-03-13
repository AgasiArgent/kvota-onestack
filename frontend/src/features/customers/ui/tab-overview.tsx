import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Customer, CustomerStats } from "@/entities/customer";

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
