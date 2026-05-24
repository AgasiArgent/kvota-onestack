"use client";

import type { KpProposal } from "@/entities/kp-proposal";

import styles from "./kp-form.module.css";

interface SectionContactsProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
}

export function SectionContacts({ data, setData }: SectionContactsProps) {
  const set =
    (key: keyof KpProposal) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setData((prev) => ({ ...prev, [key]: e.target.value }));
    };

  return (
    <div>
      <div className={styles.field}>
        <div className={styles.fieldLabel}>Для заметок (страница 2)</div>
        <textarea
          className={styles.textarea}
          value={data.notes2}
          onChange={set("notes2")}
          rows={3}
        />
      </div>

      <div className={styles.sectionTitle}>
        <div className={styles.sectionTitleDot} />
        Контакты (страница 2)
      </div>
      <div className={styles.row2}>
        <Field label="Телефон">
          <input
            className={styles.input}
            value={data.contact_phone}
            onChange={set("contact_phone")}
          />
        </Field>
        <Field label="E-mail">
          <input
            className={styles.input}
            value={data.contact_email}
            onChange={set("contact_email")}
          />
        </Field>
      </div>
      <div className={styles.row2}>
        <Field label="Сайт">
          <input
            className={styles.input}
            value={data.contact_site}
            onChange={set("contact_site")}
          />
        </Field>
        <Field label="Адрес">
          <input
            className={styles.input}
            value={data.contact_address}
            onChange={set("contact_address")}
          />
        </Field>
      </div>

      <div className={styles.sectionTitle}>
        <div className={styles.sectionTitleDot} />
        Подвал страницы 2
      </div>
      <div className={styles.row2}>
        <Field label="Телефон в подвале">
          <input
            className={styles.input}
            value={data.foot_phone}
            onChange={set("foot_phone")}
            placeholder="8-800-350-21-34"
          />
        </Field>
        <Field label="Сайт в подвале">
          <input
            className={styles.input}
            value={data.foot_site}
            onChange={set("foot_site")}
            placeholder="www.masterbearing.ru"
          />
        </Field>
      </div>
      <Field label="E-mail в подвале">
        <input
          className={styles.input}
          value={data.foot_email}
          onChange={set("foot_email")}
          placeholder="order@masterbearing.ru"
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
