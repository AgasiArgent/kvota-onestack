"use client";

/**
 * "Информация о предложении" — header / meta fields (REQ-3).
 * Twelve text inputs covering supplier identity, contacts, commercial
 * terms, and totals. Each input writes through to the parent setData.
 */

import {
  CURRENCIES,
  currencySymbol,
} from "@/entities/kp-proposal";
import type { CurrencyCode, KpProposal } from "@/entities/kp-proposal";

import styles from "./kp-form.module.css";

interface SectionOfferProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
}

export function SectionOffer({ data, setData }: SectionOfferProps) {
  const set =
    (key: keyof KpProposal) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setData((prev) => ({ ...prev, [key]: e.target.value }));
    };

  return (
    <div>
      <div className={styles.sectionTitle}>
        <div className={styles.sectionTitleDot} />
        Информация о предложении
      </div>

      <div className={styles.row2}>
        <Field label="Поставщик">
          <input
            className={styles.input}
            value={data.supplier}
            onChange={set("supplier")}
            placeholder="ООО «Мастер Беринг»"
          />
        </Field>
        <Field label="Менеджер отдела продаж">
          <input
            className={styles.input}
            value={data.manager}
            onChange={set("manager")}
            placeholder="Иванов И. И."
          />
        </Field>
      </div>

      <div className={styles.row2}>
        <Field label="Телефон">
          <input
            className={styles.input}
            value={data.phone}
            onChange={set("phone")}
            placeholder="+7 (___) ___-__-__"
          />
        </Field>
        <Field label="E-mail">
          <input
            className={styles.input}
            value={data.email}
            onChange={set("email")}
            placeholder="manager@masterbearing.ru"
          />
        </Field>
      </div>

      <div className={styles.row2}>
        <Field label="Адрес поставки">
          <input
            className={styles.input}
            value={data.address}
            onChange={set("address")}
            placeholder="Москва, ..."
          />
        </Field>
        <Field label="Базис поставки">
          <input
            className={styles.input}
            value={data.basis}
            onChange={set("basis")}
            placeholder="DDP / EXW / FCA"
          />
        </Field>
      </div>

      <div className={styles.row2}>
        <Field label="Условия оплаты">
          <input
            className={styles.input}
            value={data.payment}
            onChange={set("payment")}
            placeholder="50% предоплата / 50%..."
          />
        </Field>
        <Field label="Дата предоставления">
          <input
            className={styles.input}
            value={data.date}
            onChange={set("date")}
            placeholder="21.05.2026"
          />
        </Field>
      </div>

      <div className={styles.row3}>
        <Field label="Срок поставки">
          <input
            className={styles.input}
            value={data.lead}
            onChange={set("lead")}
            placeholder="60 рабочих дней"
          />
        </Field>
        <Field label="Валюта">
          <select
            className={styles.input}
            value={data.currency}
            onChange={(e) =>
              setData((prev) => ({
                ...prev,
                currency: e.target.value as CurrencyCode,
              }))
            }
          >
            {CURRENCIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.code} {c.symbol !== c.code ? c.symbol : ""}
              </option>
            ))}
          </select>
        </Field>
        <Field label={`Сумма КП, ${currencySymbol(data.currency)}`}>
          <input
            className={styles.input}
            value={data.amount}
            onChange={set("amount")}
            inputMode="numeric"
            placeholder="0"
          />
        </Field>
      </div>

      <Field label="Подзаголовок">
        <input
          className={styles.input}
          value={data.subtitle}
          onChange={set("subtitle")}
          placeholder="на поставку крупной спецтехники"
        />
      </Field>

      <Field label="Цена включает">
        <textarea
          className={styles.textarea}
          value={data.price_includes}
          onChange={set("price_includes")}
          placeholder="Доставка, НДС 20%, упаковка..."
          rows={2}
        />
      </Field>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.field}>
      <div className={styles.fieldLabel}>{label}</div>
      {children}
    </div>
  );
}
