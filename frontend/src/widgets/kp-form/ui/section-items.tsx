"use client";

/**
 * Equipment items table (REQ-4) — dynamic add/remove rows with auto row
 * sum and grand total.
 */

import { calcRowTotal, fmtRu } from "@/entities/kp-proposal";
import type { KpItem, KpProposal } from "@/entities/kp-proposal";

import { useDynamicList } from "../lib/use-dynamic-list";
import styles from "./kp-form.module.css";

interface SectionItemsProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
}

const EMPTY_ITEM: KpItem = { name: "", model: "", qty: "", price: "" };

export function SectionItems({ data, setData }: SectionItemsProps) {
  const setItems = (next: KpItem[]) => {
    setData((prev) => ({ ...prev, items: next }));
  };
  const { add, remove, update } = useDynamicList<KpItem>(data.items, setItems);

  return (
    <div>
      <div className={styles.sectionTitle}>
        <div className={styles.sectionTitleDot} />
        Перечень техники и стоимость
      </div>

      <div className={styles.items} role="grid">
        <div
          className={`${styles.itemsRow} ${styles.itemsHead}`}
          role="row"
          aria-label="Заголовок таблицы позиций"
        >
          <div>№</div>
          <div>Наименование</div>
          <div>Модель / характеристики</div>
          <div>Кол-во</div>
          <div>Цена за ед.</div>
          <div>Сумма</div>
          <div />
        </div>
        {data.items.map((row, i) => {
          const total = calcRowTotal(row);
          return (
            <div className={styles.itemsRow} role="row" key={i}>
              <div className={styles.cell}>
                <input
                  className={styles.cellInput}
                  value={String(i + 1)}
                  readOnly
                  aria-label="Номер строки"
                />
              </div>
              <div className={styles.cell}>
                <input
                  className={styles.cellInput}
                  value={row.name}
                  onChange={(e) => update(i, { ...row, name: e.target.value })}
                  placeholder="Бульдозер"
                  aria-label="Наименование"
                />
              </div>
              <div className={styles.cell}>
                <input
                  className={styles.cellInput}
                  value={row.model}
                  onChange={(e) => update(i, { ...row, model: e.target.value })}
                  placeholder="Shantui SD16"
                  aria-label="Модель"
                />
              </div>
              <div className={`${styles.cell} ${styles.cellNum}`}>
                <input
                  className={styles.cellInput}
                  value={row.qty}
                  onChange={(e) => update(i, { ...row, qty: e.target.value })}
                  inputMode="numeric"
                  aria-label="Количество"
                />
              </div>
              <div className={`${styles.cell} ${styles.cellNum}`}>
                <input
                  className={styles.cellInput}
                  value={row.price}
                  onChange={(e) => update(i, { ...row, price: e.target.value })}
                  inputMode="numeric"
                  aria-label="Цена за единицу"
                />
              </div>
              <div className={`${styles.cell} ${styles.cellNum}`}>
                <input
                  className={styles.cellInput}
                  value={total !== null ? fmtRu(total) : ""}
                  readOnly
                  aria-label="Сумма строки"
                />
              </div>
              <button
                className={styles.removeBtn}
                onClick={() => remove(i)}
                type="button"
                aria-label="Удалить строку"
                title="Удалить строку"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
      <button
        className={styles.addBtn}
        onClick={() => add({ ...EMPTY_ITEM })}
        type="button"
      >
        + Добавить позицию
      </button>
    </div>
  );
}
