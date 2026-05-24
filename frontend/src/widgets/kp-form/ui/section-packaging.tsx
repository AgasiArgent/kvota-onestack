"use client";

import type { KpPackagingItem, KpProposal } from "@/entities/kp-proposal";

import { useDynamicList } from "../lib/use-dynamic-list";
import styles from "./kp-form.module.css";

interface SectionPackagingProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
}

const EMPTY_PKG: KpPackagingItem = { text: "", checked: false };

export function SectionPackaging({ data, setData }: SectionPackagingProps) {
  const setPackaging = (next: KpPackagingItem[]) => {
    setData((prev) => ({ ...prev, packaging: next }));
  };
  const { add, remove, update } = useDynamicList<KpPackagingItem>(
    data.packaging,
    setPackaging,
  );

  return (
    <div>
      <div className={styles.sectionTitle}>
        <div className={styles.sectionTitleDot} />
        Комплектация
      </div>
      <div className={styles.editableList}>
        {data.packaging.map((item, i) => (
          <div className={styles.editableListRowCheck} key={i}>
            <input
              type="checkbox"
              className={styles.editableListCheck}
              checked={item.checked}
              onChange={(e) => update(i, { ...item, checked: e.target.checked })}
              aria-label="Включено в комплектацию"
            />
            <input
              className={styles.input}
              value={item.text}
              onChange={(e) => update(i, { ...item, text: e.target.value })}
              placeholder="Отвал прямой 3,4 м"
            />
            <button
              className={styles.removeBtn}
              onClick={() => remove(i)}
              type="button"
              aria-label="Удалить позицию комплектации"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        className={styles.addBtn}
        onClick={() => add({ ...EMPTY_PKG })}
        type="button"
      >
        + Добавить позицию
      </button>
    </div>
  );
}
