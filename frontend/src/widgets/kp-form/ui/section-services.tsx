"use client";

import type { KpProposal, KpServices } from "@/entities/kp-proposal";

import styles from "./kp-form.module.css";

interface SectionServicesProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
}

// REQ-9.3 — fixed order, Russian labels.
const SERVICE_FIELDS: ReadonlyArray<{ key: keyof KpServices; label: string }> = [
  { key: "delivery", label: "Доставка" },
  { key: "training", label: "Обучение операторов" },
  { key: "supervision", label: "Шеф-монтаж" },
  { key: "warranty", label: "Расширенная гарантия" },
  { key: "commissioning", label: "Пусконаладочные работы" },
  { key: "service", label: "Сервисное обслуживание" },
];

export function SectionServices({ data, setData }: SectionServicesProps) {
  const toggle = (key: keyof KpServices) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setData((prev) => ({
      ...prev,
      services: { ...prev.services, [key]: e.target.checked },
    }));
  };

  return (
    <div>
      <div className={styles.sectionTitle}>
        <div className={styles.sectionTitleDot} />
        Дополнительные услуги (по запросу)
      </div>
      <div className={styles.checkSet}>
        {SERVICE_FIELDS.map(({ key, label }) => (
          <label className={styles.checkSetLabel} key={key}>
            <input
              type="checkbox"
              checked={data.services[key]}
              onChange={toggle(key)}
            />
            {label}
          </label>
        ))}
      </div>
    </div>
  );
}
