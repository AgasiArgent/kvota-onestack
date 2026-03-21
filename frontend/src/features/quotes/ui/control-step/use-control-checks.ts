"use client";

import { useMemo } from "react";
import type { CalcSummaryRow, DocumentRow } from "./use-control-data";

export type CheckStatus = "ok" | "warning" | "error" | "info";

export interface CheckResult {
  id: string;
  label: string;
  value: string;
  status: CheckStatus;
  details: string | null;
}

interface QuoteInput {
  deal_type: string | null;
  currency: string | null;
  workflow_status: string | null;
}

interface ItemInput {
  supplier_country: string | null;
  price_includes_vat: boolean | null;
  purchase_price_original: number | null;
  quantity: number;
  invoice_id: string | null;
}

interface CalcVariablesInput {
  markup: number | null;
  advance_from_client: number | null;
  supplier_advance: number | null;
  forex_risk_percent: number | null;
  lpr_reward: number | null;
  payment_terms_code: string | null;
  offer_sale_type: string | null;
  offer_incoterms: string | null;
  decision_maker_reward: number | null;
  customs_duty: number | null;
  customs_rate: number | null;
}

// ---------------------------------------------------------------------------
// Minimum markup thresholds by deal type and payment terms
// ---------------------------------------------------------------------------

const SUPPLY_MARKUP_BY_TERMS: Record<string, number> = {
  prepaid_100: 12,
  split_50_50: 15,
  deferred: 18,
};

const TRANSIT_MARKUP_BY_TERMS: Record<string, number> = {
  prepaid_100: 8,
  split_50_50: 10,
  deferred: 12,
};

const VAT_WARNING_COUNTRIES = new Set(["TR", "PL", "LT"]);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function getVar<K extends keyof CalcVariablesInput>(
  vars: Record<string, unknown> | null,
  key: K
): CalcVariablesInput[K] {
  if (!vars) return null as CalcVariablesInput[K];
  return (vars[key] ?? null) as CalcVariablesInput[K];
}

function resolvePaymentTermsBucket(
  paymentTermsCode: string | null,
  advanceFromClient: number | null
): string {
  if (paymentTermsCode) {
    const code = paymentTermsCode.toLowerCase();
    if (code.includes("100") || code.includes("prepaid")) return "prepaid_100";
    if (code.includes("50") || code.includes("split")) return "split_50_50";
    if (code.includes("defer") || code.includes("отсроч")) return "deferred";
  }
  // Fall back to advance percentage
  const advance = advanceFromClient ?? 0;
  if (advance >= 100) return "prepaid_100";
  if (advance >= 40 && advance <= 60) return "split_50_50";
  return "deferred";
}

function formatPercent(value: number | null): string {
  if (value === null) return "—";
  return `${value}%`;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useControlChecks(
  quote: QuoteInput,
  items: ItemInput[],
  calcVariables: Record<string, unknown> | null,
  calcSummary: CalcSummaryRow | null,
  invoiceDocuments: Map<string, DocumentRow>
): CheckResult[] {
  return useMemo(() => {
    const checks: CheckResult[] = [];

    // 1. Markup vs payment terms
    const markup = toNumber(getVar(calcVariables, "markup"));
    const paymentTermsCode = getVar(calcVariables, "payment_terms_code");
    const advanceFromClient = toNumber(
      getVar(calcVariables, "advance_from_client")
    );
    const termsBucket = resolvePaymentTermsBucket(
      paymentTermsCode,
      advanceFromClient
    );
    const dealType = (quote.deal_type ?? "supply").toLowerCase();
    const isTransit = dealType === "transit" || dealType === "транзит";
    const thresholds = isTransit
      ? TRANSIT_MARKUP_BY_TERMS
      : SUPPLY_MARKUP_BY_TERMS;
    const minMarkup = thresholds[termsBucket] ?? thresholds.deferred;

    const markupStatus: CheckStatus =
      markup !== null && markup >= minMarkup ? "ok" : "error";
    checks.push({
      id: "markup",
      label: "Наценка vs условия оплаты",
      value: `${formatPercent(markup)} (мин. ${minMarkup}%)`,
      status: markupStatus,
      details:
        markupStatus === "error"
          ? `Наценка ${formatPercent(markup)} ниже минимума ${minMarkup}% для ${isTransit ? "транзита" : "поставки"} (${termsBucket})`
          : null,
    });

    // 2. Invoice coverage
    const totalItems = items.length;
    const itemsWithInvoice = items.filter((i) => i.invoice_id !== null);
    const coveredCount = itemsWithInvoice.length;
    const invoiceIdsInUse = new Set(
      itemsWithInvoice
        .map((i) => i.invoice_id)
        .filter((id): id is string => id !== null)
    );
    const invoicesWithScans = Array.from(invoiceIdsInUse).filter((id) =>
      invoiceDocuments.has(id)
    );
    const allHaveScans =
      invoiceIdsInUse.size > 0 &&
      invoicesWithScans.length === invoiceIdsInUse.size;

    let invoiceStatus: CheckStatus;
    let invoiceValue: string;
    let invoiceDetails: string | null = null;

    if (totalItems === 0) {
      invoiceStatus = "info";
      invoiceValue = "Нет позиций";
    } else if (coveredCount === 0) {
      invoiceStatus = "info";
      invoiceValue = "Нет инвойсов";
      invoiceDetails = "Ни одна позиция не привязана к инвойсу";
    } else if (coveredCount < totalItems) {
      invoiceStatus = "warning";
      invoiceValue = `${coveredCount} из ${totalItems} позиций`;
      invoiceDetails = `${totalItems - coveredCount} позиций без инвойса`;
    } else if (!allHaveScans) {
      invoiceStatus = "warning";
      invoiceValue = `${coveredCount}/${totalItems}, сканы: ${invoicesWithScans.length}/${invoiceIdsInUse.size}`;
      invoiceDetails = `${invoiceIdsInUse.size - invoicesWithScans.length} инвойсов без сканов`;
    } else {
      invoiceStatus = "ok";
      invoiceValue = `${coveredCount}/${totalItems} позиций, все со сканами`;
    }

    checks.push({
      id: "invoices",
      label: "Покрытие инвойсами",
      value: invoiceValue,
      status: invoiceStatus,
      details: invoiceDetails,
    });

    // 3. Country + VAT warnings
    const flaggedItems = items.filter(
      (item) =>
        item.supplier_country !== null &&
        VAT_WARNING_COUNTRIES.has(item.supplier_country.toUpperCase())
    );
    const flaggedCountries = Array.from(
      new Set(
        flaggedItems.map((i) => (i.supplier_country ?? "").toUpperCase())
      )
    );

    checks.push({
      id: "vat",
      label: "Страна + НДС",
      value:
        flaggedCountries.length > 0
          ? `Внимание: ${flaggedCountries.join(", ")}`
          : "Ок",
      status: flaggedCountries.length > 0 ? "warning" : "ok",
      details:
        flaggedCountries.length > 0
          ? `${flaggedItems.length} позиций из ${flaggedCountries.join(", ")} — сложности с возвратом НДС`
          : null,
    });

    // 4. Logistics
    const totalLogistics = calcSummary?.calc_v16_total_logistics ?? null;
    const logisticsPresent = totalLogistics !== null && totalLogistics > 0;

    checks.push({
      id: "logistics",
      label: "Логистика",
      value: logisticsPresent
        ? `$${totalLogistics.toLocaleString("ru-RU", { maximumFractionDigits: 2 })}`
        : "Не заполнена",
      status: logisticsPresent ? "ok" : "warning",
      details: logisticsPresent
        ? null
        : "Стоимость логистики не рассчитана или равна нулю",
    });

    // 5. Customs
    const customsDuty = toNumber(getVar(calcVariables, "customs_duty"));
    const customsRate = toNumber(getVar(calcVariables, "customs_rate"));
    const customsSet =
      (customsDuty !== null && customsDuty > 0) ||
      (customsRate !== null && customsRate > 0);

    checks.push({
      id: "customs",
      label: "Таможенная пошлина",
      value: customsSet
        ? customsRate !== null
          ? `${customsRate}%`
          : `$${(customsDuty ?? 0).toLocaleString("ru-RU", { maximumFractionDigits: 2 })}`
        : "Не указана",
      status: customsSet ? "ok" : "warning",
      details: customsSet
        ? null
        : "Таможенная пошлина или ставка не указаны в параметрах расчёта",
    });

    // 6. Forex risk
    const supplierAdvance = toNumber(
      getVar(calcVariables, "supplier_advance")
    );
    const forexRiskPercent = toNumber(
      getVar(calcVariables, "forex_risk_percent")
    );

    let autoForex: number;
    const advancePct = supplierAdvance ?? advanceFromClient ?? 0;
    if (advancePct >= 100) {
      autoForex = 0;
    } else if (advancePct >= 45 && advancePct <= 55) {
      autoForex = 1.5;
    } else {
      autoForex = 3;
    }

    const effectiveForex = forexRiskPercent ?? autoForex;

    checks.push({
      id: "forex",
      label: "Валютный риск",
      value: `${effectiveForex}%`,
      status: "ok",
      details:
        forexRiskPercent !== null
          ? `Задан вручную: ${forexRiskPercent}%`
          : `Авто по предоплате ${advancePct}%: ${autoForex}%`,
    });

    // 7. Kickback / LPR
    const lprReward = toNumber(getVar(calcVariables, "lpr_reward"));
    const dmReward = toNumber(
      getVar(calcVariables, "decision_maker_reward")
    );
    const hasKickback =
      (lprReward !== null && lprReward > 0) ||
      (dmReward !== null && dmReward > 0);

    const kickbackParts: string[] = [];
    if (lprReward !== null && lprReward > 0)
      kickbackParts.push(`LPR: ${lprReward}%`);
    if (dmReward !== null && dmReward > 0)
      kickbackParts.push(`ЛПР: ${dmReward}%`);

    checks.push({
      id: "kickback",
      label: "Вознаграждение / LPR",
      value: hasKickback ? kickbackParts.join(", ") : "Нет",
      status: hasKickback ? "warning" : "ok",
      details: hasKickback ? "Требует согласования" : null,
    });

    return checks;
  }, [quote, items, calcVariables, calcSummary, invoiceDocuments]);
}
