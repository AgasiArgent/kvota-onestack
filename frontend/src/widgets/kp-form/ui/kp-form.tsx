"use client";

/**
 * Left-pane composition. Threads `data`/`setData` into each section and
 * exposes `onClear`/`onLoadExample` for the form header buttons.
 */

import type { KpProposal } from "@/entities/kp-proposal";

import { FormHeader } from "./form-header";
import styles from "./kp-form.module.css";
import { SectionConditions } from "./section-conditions";
import { SectionContacts } from "./section-contacts";
import { SectionItems } from "./section-items";
import { SectionNotes } from "./section-notes";
import { SectionOffer } from "./section-offer";
import { SectionPackaging } from "./section-packaging";
import { SectionServices } from "./section-services";
import { SectionSpecs } from "./section-specs";

interface KpFormProps {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
  onClear: () => void;
  onLoadExample: () => void;
}

export function KpForm({
  data,
  setData,
  onClear,
  onLoadExample,
}: KpFormProps) {
  return (
    <div className={styles.formRoot}>
      <FormHeader onClear={onClear} onLoadExample={onLoadExample} />
      <div className={styles.formBody}>
        <SectionOffer data={data} setData={setData} />
        <SectionItems data={data} setData={setData} />
        <SectionNotes data={data} setData={setData} />
        <SectionSpecs data={data} setData={setData} />
        <SectionPackaging data={data} setData={setData} />
        <SectionConditions data={data} setData={setData} />
        <SectionServices data={data} setData={setData} />
        <SectionContacts data={data} setData={setData} />
        <div className={styles.helper}>
          Поля заполняются вручную. Состояние сохраняется в браузере
          (localStorage) и восстанавливается при следующем заходе.
        </div>
      </div>
    </div>
  );
}
