"use client";

import type { KpProposal } from "@/entities/kp-proposal";

import { useDynamicList } from "../lib/use-dynamic-list";
import styles from "./kp-form.module.css";

interface SectionConditionsProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
}

export function SectionConditions({ data, setData }: SectionConditionsProps) {
  const setConditions = (next: string[]) => {
    setData((prev) => ({ ...prev, conditions: next }));
  };
  const { add, remove, update } = useDynamicList<string>(
    data.conditions,
    setConditions,
  );

  return (
    <div>
      <div className={styles.sectionTitle}>
        <div className={styles.sectionTitleDot} />
        Условия и гарантии
      </div>
      <div className={styles.editableList}>
        {data.conditions.map((value, i) => (
          <div className={styles.editableListRow} key={i}>
            <div className={styles.editableListBullet} />
            <input
              className={styles.input}
              value={value}
              onChange={(e) => update(i, e.target.value)}
              placeholder="Гарантия 12 месяцев или 2000 моточасов"
            />
            <button
              className={styles.removeBtn}
              onClick={() => remove(i)}
              type="button"
              aria-label="Удалить условие"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button className={styles.addBtn} onClick={() => add("")} type="button">
        + Добавить условие
      </button>
    </div>
  );
}
