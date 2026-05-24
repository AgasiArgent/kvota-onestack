"use client";

import type { KpProposal } from "@/entities/kp-proposal";

import { useDynamicList } from "../lib/use-dynamic-list";
import styles from "./kp-form.module.css";

interface SectionSpecsProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
}

export function SectionSpecs({ data, setData }: SectionSpecsProps) {
  const setSpecs = (next: string[]) => {
    setData((prev) => ({ ...prev, specs: next }));
  };
  const { add, remove, update } = useDynamicList<string>(data.specs, setSpecs);

  return (
    <div>
      <div className={styles.sectionTitle}>
        <div className={styles.sectionTitleDot} />
        Основные характеристики
      </div>
      <div className={styles.editableList}>
        {data.specs.map((value, i) => (
          <div className={styles.editableListRow} key={i}>
            <div className={styles.editableListBullet} />
            <input
              className={styles.input}
              value={value}
              onChange={(e) => update(i, e.target.value)}
              placeholder="Мощность двигателя — 162 л.с."
            />
            <button
              className={styles.removeBtn}
              onClick={() => remove(i)}
              type="button"
              aria-label="Удалить характеристику"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button className={styles.addBtn} onClick={() => add("")} type="button">
        + Добавить характеристику
      </button>
    </div>
  );
}
