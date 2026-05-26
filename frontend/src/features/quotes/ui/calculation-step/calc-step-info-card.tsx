"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Info, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { createClient } from "@/shared/lib/supabase/client";

/**
 * CalcStepInfoCard — info panel sitting above the items table on the
 * calc-step page (Testing 2 rows 36 + 48).
 *
 * Shows three things the salesperson needs to see at a glance before
 * pressing «Рассчитать»:
 *   - Per-invoice logistics cost (auto-pulled from the route constructor).
 *   - Customs duties + ТН ВЭД per item (collected on the customs step).
 *   - Certifications attached to the quote (type + cost + currency).
 *
 * When logistics is empty for an invoice we show a warning badge with a
 * deep link to the logistics step. The warning is informational — it does
 * NOT block the calc button (per locked product decision 2026-05-25:
 * «warning is informational», don't block UI).
 *
 * Data source: GET /api/quotes/{id}/calc-step-info — single endpoint that
 * fans out to logistics_route_segments, quote_items, quote_certificates,
 * exchange_rates. See api/calc_step_info.py.
 */

interface LogisticsRow {
  invoice_id: string;
  invoice_number: string;
  cost: number;
  currency: string;
  segment_count: number;
  is_filled: boolean;
  missing_rates: string[];
}

interface CustomsRow {
  item_id: string;
  brand: string | null;
  product_name: string | null;
  hs_code: string | null;
  customs_duty: number | null;
}

interface CertificationRow {
  id: string;
  type: string | null;
  display_name: string | null;
  cost: number;
  currency: string;
}

interface CalcStepInfoData {
  logistics_per_invoice: LogisticsRow[];
  customs: CustomsRow[];
  certifications: CertificationRow[];
}

interface CalcStepInfoCardProps {
  quoteId: string;
  /** Stable href to the logistics step on this quote, used in the warning badge. */
  logisticsHref?: string;
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "€",
  USD: "$",
  CNY: "¥",
  RUB: "₽",
};

function fmtMoney(value: number, currency: string): string {
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  return `${formatted} ${symbol}`;
}

function fmtDuty(value: number | null): string {
  if (value == null) return "—";
  // Trailing-zero trimming: 5.0 → "5%", 7.5 → "7.5%"
  const rounded = Math.round(value * 100) / 100;
  return `${rounded}%`;
}

export function CalcStepInfoCard({ quoteId, logisticsHref }: CalcStepInfoCardProps) {
  const [data, setData] = useState<CalcStepInfoData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        // JWT auth — same pattern as calculation-action-bar.tsx.
        const supabase = createClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();

        const res = await fetch(
          `/api/quotes/${encodeURIComponent(quoteId)}/calc-step-info`,
          {
            method: "GET",
            headers: {
              ...(session?.access_token
                ? { Authorization: `Bearer ${session.access_token}` }
                : {}),
            },
            cache: "no-store",
          },
        );
        const json = await res.json();
        if (cancelled) return;
        if (!res.ok || !json.success) {
          setError(json.error?.message ?? `HTTP ${res.status}`);
          return;
        }
        setData(json.data as CalcStepInfoData);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Не удалось загрузить");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [quoteId]);

  if (loading) {
    return (
      <Card size="sm" data-testid="calc-step-info-card-loading">
        <CardContent className="pt-4 text-xs text-muted-foreground">
          Загрузка данных…
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card size="sm" data-testid="calc-step-info-card-error">
        <CardContent className="pt-4 text-xs text-destructive flex items-center gap-2">
          <AlertTriangle size={14} aria-hidden />
          <span>Ошибка загрузки информации: {error}</span>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const hasLogisticsWarning = data.logistics_per_invoice.some(
    (row) => !row.is_filled,
  );

  return (
    <Card size="sm" data-testid="calc-step-info-card">
      <CardHeader className="border-b">
        <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
          <Info size={12} aria-hidden />
          Сводка по заказу
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-3 grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Section 1: Logistics per invoice */}
        <section
          aria-labelledby="calc-info-logistics-title"
          data-testid="calc-step-info-logistics"
        >
          <h3
            id="calc-info-logistics-title"
            className="text-xs font-medium text-foreground mb-2"
          >
            Логистика по инвойсам
          </h3>
          {data.logistics_per_invoice.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Нет инвойсов в этом КП.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {data.logistics_per_invoice.map((row) => (
                <li
                  key={row.invoice_id}
                  className="flex flex-col gap-0.5"
                  data-testid={`calc-step-info-logistics-row-${row.invoice_id}`}
                >
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-medium text-foreground truncate">
                      {row.invoice_number}
                    </span>
                    {row.is_filled ? (
                      <span className="tabular-nums text-foreground">
                        {fmtMoney(row.cost, row.currency)}
                      </span>
                    ) : (
                      <Badge
                        variant="default"
                        className="bg-amber-50 text-amber-700 border border-amber-200 text-[10px] py-0 px-1.5 inline-flex items-center gap-1"
                        data-testid={`calc-step-info-logistics-warning-${row.invoice_id}`}
                      >
                        <AlertTriangle size={10} aria-hidden />
                        Не указано
                      </Badge>
                    )}
                  </div>
                  {!row.is_filled && (
                    <p className="text-[10px] text-muted-foreground leading-tight">
                      Стоимость логистики не указана — заполните на{" "}
                      {logisticsHref ? (
                        <Link
                          href={logisticsHref}
                          className="underline decoration-dotted hover:text-foreground inline-flex items-center gap-0.5"
                        >
                          логистическом этапе
                          <ExternalLink size={9} aria-hidden />
                        </Link>
                      ) : (
                        "логистическом этапе"
                      )}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
          {hasLogisticsWarning && (
            <p
              className="mt-2 text-[10px] text-muted-foreground italic"
              data-testid="calc-step-info-logistics-hint"
            >
              Расчёт можно запустить — стоимость логистики необязательна.
            </p>
          )}
        </section>

        {/* Section 2: Customs duties + ТН ВЭД */}
        <section
          aria-labelledby="calc-info-customs-title"
          data-testid="calc-step-info-customs"
        >
          <h3
            id="calc-info-customs-title"
            className="text-xs font-medium text-foreground mb-2"
          >
            Пошлины и ТН ВЭД
          </h3>
          {data.customs.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Нет позиций в КП.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {data.customs.map((row) => (
                <li
                  key={row.item_id}
                  className="flex flex-col gap-0.5 text-xs"
                  data-testid={`calc-step-info-customs-row-${row.item_id}`}
                >
                  <span className="font-medium text-foreground truncate">
                    {row.brand ? `${row.brand} ` : ""}
                    {row.product_name ?? "—"}
                  </span>
                  <span className="text-muted-foreground tabular-nums text-[11px]">
                    {row.hs_code ?? "—"} · {fmtDuty(row.customs_duty)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Section 3: Certifications */}
        <section
          aria-labelledby="calc-info-certs-title"
          data-testid="calc-step-info-certs"
        >
          <h3
            id="calc-info-certs-title"
            className="text-xs font-medium text-foreground mb-2"
          >
            Сертификация
          </h3>
          {data.certifications.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Сертификаты не добавлены.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {data.certifications.map((cert) => (
                <li
                  key={cert.id}
                  className="flex items-center justify-between gap-2 text-xs"
                  data-testid={`calc-step-info-cert-row-${cert.id}`}
                >
                  <span className="font-medium text-foreground truncate">
                    {cert.display_name ?? cert.type ?? "—"}
                  </span>
                  <span className="tabular-nums text-foreground">
                    {fmtMoney(cert.cost, cert.currency)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </CardContent>
    </Card>
  );
}
