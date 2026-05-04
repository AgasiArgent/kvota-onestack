import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

import { SpecialDutyBlock } from "../ui/special-duty-block";
import { type ResolvedRate } from "../model/types";

/**
 * Pure SSR rendering tests for SpecialDutyBlock — the frontend workspace has
 * no jsdom configured (see city-combobox.test.tsx for the rationale), so we
 * use `react-dom/server` to assert markup. Interaction (radio click) is
 * verified at runtime via localhost:3000 per
 * `reference_localhost_browser_test.md`.
 */

const VARIANT_DEFAULTS = {
  description: null,
  category_code: null,
  category_ru: null,
  condition_text: null,
  legal_document: null,
  legal_link: null,
  order_ref: null,
  is_default: false,
} as const;

function makeRate(overrides: Partial<ResolvedRate> = {}): ResolvedRate {
  return {
    payment_type: "IMPDEMP",
    value_1_number: 19.4,
    value_1_unit: "percent",
    value_1_currency: null,
    value_2_number: null,
    value_2_unit: null,
    value_2_currency: null,
    sign_1: null,
    raw_value_string: null,
    calculated_amount_rub: null,
    ...VARIANT_DEFAULTS,
    ...overrides,
  };
}

describe("SpecialDutyBlock — empty state", () => {
  it("renders nothing when variants array is empty", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toBe("");
  });
});

describe("SpecialDutyBlock — IMPDEMP full card", () => {
  const variant = makeRate({
    payment_type: "IMPDEMP",
    value_1_number: 19.4,
    order_ref:
      "Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины на стальные трубы)",
    legal_link: "https://alta.ru/tamdoc/example",
    category_code: "antidump-702",
  });

  it("renders title 'Антидемпинговая пошлина'", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[variant]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain("Антидемпинговая пошлина");
  });

  it("renders rate badge as `19.4%`", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[variant]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain("19.4%");
  });

  it("renders order_ref text", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[variant]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain("Решение 702");
  });

  it("uses orange tinted card classes", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[variant]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain("border-orange-900");
    expect(html).toContain("bg-orange-950/20");
  });

  it("renders explanation line when countryName + tnvedCode supplied", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[variant]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
        countryName="Украина"
        tnvedCode="7304292000"
      />,
    );
    expect(html).toContain("Применяется потому что");
    expect(html).toContain("Украина");
  });

  it("omits explanation line when context not supplied", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[variant]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).not.toContain("Применяется потому что");
  });

  it("renders legal_link with target=_blank", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[variant]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain('target="_blank"');
    expect(html).toContain("https://alta.ru/tamdoc/example");
  });

  it("does not render document link when legal_link is null", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[makeRate({ legal_link: null })]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).not.toContain('target="_blank"');
  });
});

describe("SpecialDutyBlock — IMPDEMP multi-variant radios", () => {
  const v1 = makeRate({
    value_1_number: 19.4,
    description: "Производитель ABC",
    category_code: "abc",
  });
  const v2 = makeRate({
    value_1_number: 24.1,
    description: "Прочие производители",
    category_code: "other",
  });

  it("renders radio inputs when multiple variants present", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[v1, v2]}
        paymentType="IMPDEMP"
        selectedCode="other"
        onSelect={() => {}}
      />,
    );
    expect(html).toContain('type="radio"');
    // React SSR may insert comment markers around expression boundaries,
    // so match the surrounding fragments instead of the joined string.
    expect(html).toContain("Варианты");
    expect(html).toContain("2");
  });

  it("marks the selectedCode radio as checked", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[v1, v2]}
        paymentType="IMPDEMP"
        selectedCode="other"
        onSelect={() => {}}
      />,
    );
    // React renders `checked` attr only on the matching input.
    const checkedCount = (html.match(/checked=""/g) ?? []).length;
    expect(checkedCount).toBe(1);
  });

  it("does not render radios when only one variant", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[v1]}
        paymentType="IMPDEMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).not.toContain('type="radio"');
    expect(html).not.toContain("Варианты");
  });
});

describe("SpecialDutyBlock — compact cards for IMPCOMP/IMPDOP/IMPTMP", () => {
  it("IMPCOMP renders compact card with red colour scheme", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[
          makeRate({
            payment_type: "IMPCOMP",
            value_1_number: 5,
            order_ref: "Решение ЕЭК 33",
          }),
        ]}
        paymentType="IMPCOMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain("Компенсационная пошлина");
    expect(html).toContain("border-red-900");
    expect(html).toContain("bg-red-950/20");
    // Compact card should NOT show the explanation line area.
    expect(html).not.toContain("Применяется потому что");
  });

  it("IMPDOP renders compact card with blue colour scheme", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[
          makeRate({
            payment_type: "IMPDOP",
            value_1_number: 7.5,
            order_ref: "Спецзащитная мера",
          }),
        ]}
        paymentType="IMPDOP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain("Специальная защитная пошлина");
    expect(html).toContain("border-blue-900");
    expect(html).toContain("bg-blue-950/20");
  });

  it("IMPTMP renders compact card with slate colour scheme", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[
          makeRate({
            payment_type: "IMPTMP",
            value_1_number: 12,
            order_ref: "Сезонная",
          }),
        ]}
        paymentType="IMPTMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain("Сезонная пошлина");
    expect(html).toContain("border-slate-700");
    expect(html).toContain("bg-slate-900/50");
  });

  it("compact card renders legal_link when provided", () => {
    const html = renderToString(
      <SpecialDutyBlock
        variants={[
          makeRate({
            payment_type: "IMPCOMP",
            value_1_number: 5,
            legal_link: "https://alta.ru/tamdoc/comp-1",
          }),
        ]}
        paymentType="IMPCOMP"
        selectedCode={null}
        onSelect={() => {}}
      />,
    );
    expect(html).toContain("https://alta.ru/tamdoc/comp-1");
    expect(html).toContain('target="_blank"');
  });
});
