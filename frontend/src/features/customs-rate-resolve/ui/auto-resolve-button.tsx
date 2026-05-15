"use client";

import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { normalizeHsCode } from "@/shared/lib/hs-code";

import { resolveRates } from "../api/resolve-rates";
import type { ApiError, ResolveRatesData } from "../model/types";

export interface AutoResolveButtonProps {
  tnvedCode: string;
  countryOksm: number | null;
  hasOriginCertificate: boolean;
  hasFtaCertificate: boolean;
  /** Optional UUID — when provided, backend updates quote_items as a side-effect. */
  quoteItemId?: string;
  /** Force `force_live=true` on the request (bypass cache). Default false. */
  forceLive?: boolean;
  onResolved: (data: ResolveRatesData) => void;
  onError: (error: ApiError) => void;
  disabled?: boolean;
  /** Override default label. Defaults to "Автоподбор ставок". */
  label?: string;
}

/**
 * Validate that a string is a 10-digit ТН ВЭД code.
 * Normalizes first so codes pasted with separators («4002 31 0000»)
 * still validate. Pure helper — testable without DOM.
 */
export function isValidTnvedCode(code: string): boolean {
  return /^\d{10}$/.test(normalizeHsCode(code));
}

export function AutoResolveButton({
  tnvedCode,
  countryOksm,
  hasOriginCertificate,
  hasFtaCertificate,
  quoteItemId,
  forceLive = false,
  onResolved,
  onError,
  disabled,
  label = "Автоподбор ставок",
}: AutoResolveButtonProps) {
  const [loading, setLoading] = useState(false);

  const codeValid = isValidTnvedCode(tnvedCode);
  const countryValid = countryOksm != null;
  const enabled = codeValid && countryValid && !loading && !disabled;

  async function handleClick() {
    // Validation UX (memory feedback_validation_ux.md): never silent fail —
    // emit a structured error if the trigger was somehow clicked while disabled.
    if (!codeValid) {
      onError({
        code: "INVALID_TNVED_CODE",
        message: "Код ТН ВЭД должен быть 10 цифр",
      });
      return;
    }
    if (!countryValid) {
      onError({
        code: "BAD_REQUEST",
        message: "Не выбрана страна происхождения",
      });
      return;
    }

    setLoading(true);
    try {
      const res = await resolveRates({
        tnved_code: normalizeHsCode(tnvedCode),
        country_oksm: countryOksm!,
        certificate: hasOriginCertificate,
        sp_certificate: hasFtaCertificate,
        has_fta_certificate: hasFtaCertificate,
        quote_item_id: quoteItemId,
        force_live: forceLive,
      });

      if (res.success && res.data) {
        onResolved(res.data);
      } else {
        onError(
          res.error ?? {
            code: "UNKNOWN",
            message: "Не удалось подобрать ставки",
          }
        );
      }
    } catch (err) {
      onError({
        code: "NETWORK_ERROR",
        message: err instanceof Error ? err.message : "Сетевая ошибка",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={handleClick}
      disabled={!enabled}
      className="gap-1.5"
      title={
        !codeValid
          ? "Заполните 10-значный код ТН ВЭД"
          : !countryValid
            ? "Выберите страну происхождения"
            : undefined
      }
    >
      {loading ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <Sparkles size={14} />
      )}
      {label}
    </Button>
  );
}
