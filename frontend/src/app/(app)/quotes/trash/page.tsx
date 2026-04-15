import { redirect } from "next/navigation";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { getSessionUser } from "@/entities/user";
import { createAdminClient } from "@/shared/lib/supabase/server";
import { TrashRestoreButton } from "@/features/quotes";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const RETENTION_DAYS = 365;

interface TrashRow {
  id: string;
  idn_quote: string | null;
  customer_name: string;
  deleted_at: string;
  deleted_by_name: string;
  age_days: number;
  days_until_purge: number;
}

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function badgeClasses(daysUntilPurge: number): string {
  if (daysUntilPurge < 7) {
    return "inline-flex items-center rounded-md bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700";
  }
  if (daysUntilPurge <= 30) {
    return "inline-flex items-center rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700";
  }
  return "inline-flex items-center rounded-md bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700";
}

function computeRetention(deletedAtIso: string): {
  age_days: number;
  days_until_purge: number;
} {
  const ageDays = Math.round(
    (Date.now() - new Date(deletedAtIso).getTime()) / 86_400_000
  );
  const daysUntilPurge = Math.max(
    0,
    Math.min(RETENTION_DAYS, RETENTION_DAYS - ageDays)
  );
  return { age_days: ageDays, days_until_purge: daysUntilPurge };
}

export default async function QuotesTrashPage() {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  // Defense-in-depth access gate: admins only. RLS also blocks soft-deleted
  // rows for non-admins, but we refuse access explicitly so the user sees
  // a permission message instead of an empty page.
  if (!user.roles.includes("admin")) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <h1 className="text-lg font-semibold text-red-800">Нет доступа</h1>
          <p className="mt-2 text-sm text-red-700">
            Только администраторы могут просматривать Корзину.
          </p>
        </div>
      </div>
    );
  }

  const admin = createAdminClient();

  // Fetch soft-deleted quotes from the base table. We intentionally bypass
  // the `active_quotes` view — we want the rows it hides.
  //
  // Types note: generated database.types.ts predates migration 279's
  // deleted_by column, so we also fetch deleted_by via a cast. Customer
  // names are fetched in a separate query (project pattern — queries.ts
  // line 264) to avoid PostgREST FK-join type friction.
  interface QuoteTrashRow {
    id: string;
    idn_quote: string | null;
    customer_id: string | null;
    deleted_at: string | null;
    deleted_by: string | null;
  }

  const { data: rawRowsData } = await admin
    .from("quotes")
    .select("id, idn_quote, customer_id, deleted_at, deleted_by")
    .not("deleted_at", "is", null)
    .order("deleted_at", { ascending: false })
    .limit(200);

  const rawRows = (rawRowsData ?? []) as unknown as QuoteTrashRow[];

  // Lookup tables: customer name by id, user full_name by user_id.
  const customerIds = Array.from(
    new Set(
      rawRows.map((r) => r.customer_id).filter((id): id is string => id !== null)
    )
  );
  const userIds = Array.from(
    new Set(
      rawRows.map((r) => r.deleted_by).filter((id): id is string => id !== null)
    )
  );

  const [customersRes, profilesRes] = await Promise.all([
    customerIds.length > 0
      ? admin.from("customers").select("id, name").in("id", customerIds)
      : Promise.resolve({ data: [] as { id: string; name: string }[] }),
    userIds.length > 0
      ? admin.from("user_profiles").select("user_id, full_name").in("user_id", userIds)
      : Promise.resolve({
          data: [] as { user_id: string; full_name: string | null }[],
        }),
  ]);

  const customerNameById = new Map<string, string>(
    (customersRes.data ?? []).map((c) => [c.id, c.name])
  );
  const nameByUserId = new Map<string, string>(
    (profilesRes.data ?? [])
      .filter((p): p is { user_id: string; full_name: string } =>
        Boolean(p.full_name)
      )
      .map((p) => [p.user_id, p.full_name])
  );

  const rows: TrashRow[] = rawRows.map((r) => {
    const deletedAtIso = r.deleted_at ?? "";
    const { age_days, days_until_purge } = deletedAtIso
      ? computeRetention(deletedAtIso)
      : { age_days: 0, days_until_purge: RETENTION_DAYS };
    const customerName = r.customer_id
      ? customerNameById.get(r.customer_id) ?? "—"
      : "—";
    const deletedByName = r.deleted_by
      ? nameByUserId.get(r.deleted_by) ?? "—"
      : "—";

    return {
      id: r.id,
      idn_quote: r.idn_quote,
      customer_name: customerName,
      deleted_at: deletedAtIso,
      deleted_by_name: deletedByName,
      age_days,
      days_until_purge,
    };
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Корзина</h1>
        <p className="mt-1 text-sm text-gray-600">
          Удалённые коммерческие предложения. Автоматическое удаление через{" "}
          {RETENTION_DAYS} дней после отметки.
        </p>
      </div>

      {rows.length === 0 ? (
        <div className="flex min-h-[40vh] flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 bg-gray-50 p-10 text-center">
          <Trash2 className="h-10 w-10 text-gray-400" />
          <p className="mt-4 text-base font-medium text-gray-700">
            Корзина пуста
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Удалённые КП будут отображаться здесь.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>№ КП</TableHead>
                <TableHead>Клиент</TableHead>
                <TableHead>Удалено</TableHead>
                <TableHead>Кто удалил</TableHead>
                <TableHead>Осталось дней</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-mono">
                    <Link
                      href={`/quotes/${row.id}`}
                      className="text-blue-600 hover:underline"
                    >
                      {row.idn_quote ?? row.id.slice(0, 8)}
                    </Link>
                  </TableCell>
                  <TableCell>{row.customer_name}</TableCell>
                  <TableCell className="text-sm text-gray-600">
                    {formatDateTime(row.deleted_at)}
                  </TableCell>
                  <TableCell className="text-sm text-gray-600">
                    {row.deleted_by_name}
                  </TableCell>
                  <TableCell>
                    <span className={badgeClasses(row.days_until_purge)}>
                      {row.days_until_purge} дн.
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <TrashRestoreButton
                      quoteId={row.id}
                      quoteIdn={row.idn_quote ?? row.id.slice(0, 8)}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
