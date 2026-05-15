"use client";

import { useState } from "react";
import { ExternalLink, Loader2, ScrollText } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { normalizeHsCode } from "@/shared/lib/hs-code";

import {
  fetchMeasures,
  type NonTariffMeasure,
} from "../api/fetch-measures";

export interface MeasuresListProps {
  tnvedCode: string;
  countryOksm: number | null;
  mode?: "import" | "export";
}

interface MeasuresState {
  status: "idle" | "loading" | "loaded" | "error";
  measures: NonTariffMeasure[];
  error: string | null;
}

const INITIAL_STATE: MeasuresState = {
  status: "idle",
  measures: [],
  error: null,
};

/**
 * Allow-list of known error codes returned by /api/customs/non-tariff-measures.
 * For any code outside this set we show a static fallback message instead of
 * echoing server text — avoids leaking stack traces / DB column names through
 * an unexpected error branch (review fix L2).
 */
const KNOWN_ERROR_MESSAGES: Record<string, string> = {
  UNAUTHORIZED: "Необходима авторизация",
  FORBIDDEN: "Недостаточно прав для просмотра мер",
  ALTA_UNAVAILABLE:
    "Alta API недоступен, попробуйте позже",
  BAD_REQUEST: "Некорректный запрос",
  INVALID_TNVED_CODE: "Неверный код ТН ВЭД",
  INVALID_OKSM: "Неверный код страны",
  DB_ERROR: "Ошибка базы данных, попробуйте позже",
};

function resolveErrorMessage(code: string | undefined): string {
  if (code && code in KNOWN_ERROR_MESSAGES) {
    return KNOWN_ERROR_MESSAGES[code];
  }
  return "Не удалось получить регуляторную справку";
}

/**
 * Pull-trigger list of non-tariff regulation measures.
 *
 * The button is the explicit user action that triggers the billed Alta call
 * (~3₽). Subsequent re-renders do NOT auto-refetch — user must click the
 * "Обновить" button. This matches gotcha #5 from the spec.
 */
export function MeasuresList({
  tnvedCode,
  countryOksm,
  mode = "import",
}: MeasuresListProps) {
  const [state, setState] = useState<MeasuresState>(INITIAL_STATE);

  const codeReady = /^\d{10}$/.test(normalizeHsCode(tnvedCode));
  const countryReady = countryOksm != null;
  const canFetch = codeReady && countryReady && state.status !== "loading";

  async function handleFetch() {
    if (!canFetch || countryOksm == null) return;
    setState({ status: "loading", measures: [], error: null });
    try {
      const res = await fetchMeasures({
        tnved_code: normalizeHsCode(tnvedCode),
        country_oksm: countryOksm,
        mode,
      });
      if (res.success && res.data) {
        setState({
          status: "loaded",
          measures: res.data.measures,
          error: null,
        });
      } else {
        // Allow-list known error codes; never echo server message verbatim
        // for unknown codes (review fix L2 — avoid leaking stack traces).
        const msg = resolveErrorMessage(res.error?.code);
        toast.error(msg);
        setState({ status: "error", measures: [], error: msg });
      }
    } catch {
      // Network / parse failure — show a generic Russian message and discard
      // any raw error text (review fix L2).
      const msg = "Сетевая ошибка, попробуйте позже";
      toast.error(msg);
      setState({ status: "error", measures: [], error: msg });
    }
  }

  if (state.status === "idle") {
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/20 p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-start gap-2">
            <ScrollText
              size={16}
              className="mt-0.5 shrink-0 text-muted-foreground"
            />
            <div>
              <div className="text-sm font-medium text-foreground">
                Регуляторная справка Alta
              </div>
              <div className="text-xs text-muted-foreground">
                Меры, условия льгот и ссылки на нормативные документы. Запрос тарифицируется отдельно (~3₽).
              </div>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleFetch}
            disabled={!canFetch}
            title={
              !codeReady
                ? "Заполните 10-значный код ТН ВЭД"
                : !countryReady
                  ? "Выберите страну происхождения"
                  : undefined
            }
          >
            Показать справку
          </Button>
        </div>
      </div>
    );
  }

  if (state.status === "loading") {
    return (
      <div className="rounded-md border border-border bg-card p-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={14} className="animate-spin" />
          Загрузка справки из Alta…
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-destructive">
            {state.error ?? "Ошибка загрузки"}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleFetch}
            disabled={!canFetch}
          >
            Повторить
          </Button>
        </div>
      </div>
    );
  }

  // loaded
  if (state.measures.length === 0) {
    return (
      <div className="rounded-md border border-border bg-card p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-muted-foreground">
            Нет регуляторных записей для этого кода и страны.
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleFetch}
            disabled={!canFetch}
          >
            Обновить
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-card p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-medium text-foreground">
          Регуляторная справка Alta ({state.measures.length})
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleFetch}
          disabled={!canFetch}
        >
          Обновить
        </Button>
      </div>
      <ul className="flex flex-col gap-2">
        {state.measures.map((m, idx) => (
          <li
            key={`${m.measure_type}-${idx}`}
            className="rounded-md border border-border bg-background p-2"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium text-foreground">
                {m.name}
              </span>
              <Badge variant="outline" className="shrink-0 text-[10px]">
                {m.measure_type}
              </Badge>
            </div>
            {m.description && (
              <div className="mt-1 text-xs text-muted-foreground">
                {m.description}
              </div>
            )}
            {(m.document_basis || m.document_link) && (
              <div className="mt-1.5 flex items-center gap-2 text-xs">
                {m.document_basis && (
                  <span className="text-muted-foreground">
                    {m.document_basis}
                  </span>
                )}
                {m.document_link && (
                  <a
                    href={m.document_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-accent hover:underline"
                  >
                    Документ
                    <ExternalLink size={11} />
                  </a>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
