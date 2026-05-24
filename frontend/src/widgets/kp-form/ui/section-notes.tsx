"use client";

import type { KpProposal } from "@/entities/kp-proposal";
import styles from "./kp-form.module.css";

interface SectionNotesProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
}

export function SectionNotes({ data, setData }: SectionNotesProps) {
  return (
    <div className={styles.field}>
      <div className={styles.fieldLabel}>
        Примечания / Дополнительная информация
      </div>
      <textarea
        className={styles.textarea}
        value={data.notes}
        onChange={(e) =>
          setData((prev) => ({ ...prev, notes: e.target.value }))
        }
        rows={3}
        placeholder="Любые уточнения, сноски..."
      />
    </div>
  );
}
