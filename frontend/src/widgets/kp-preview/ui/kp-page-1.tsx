/**
 * Page 1 of the КП preview — header bars, hero, info grid, items table,
 * notes box, four-feature footer strip.
 *
 * Mirrors `KpPage1.jsx` from the design prototype, ported into a CSS
 * Module + the TypeScript types from `entities/kp-proposal`. Number
 * formatting goes through `fmtRu` so the preview matches the backend's
 * `_fmt_ru` output 1:1.
 */

import type { ReactNode } from "react";

import {
  BRANDING,
  calcGrandTotal,
  calcRowTotal,
  currencySymbol,
  fmtRu,
  headlineSuffix,
} from "@/entities/kp-proposal";
import type { KpProposal } from "@/entities/kp-proposal";

import {
  Cal,
  Clock,
  Cog,
  Doc,
  Handshake,
  List,
  Mail,
  Phone,
  Pin,
  Pkg,
  Ruble,
  Shield,
  ShieldCheck,
  ShieldDoc,
  Truck,
  UserBadge,
  UserTie,
} from "./icons";
import { HeavyMachineryIllu } from "./illustrations";
import styles from "./kp-preview.module.css";
import { MasterBearingMark } from "./master-bearing-mark";

interface KpFieldProps {
  icon: ReactNode;
  label: string;
  value: string;
  suffix?: string;
  tall?: boolean;
}

function KpField({ icon, label, value, suffix, tall }: KpFieldProps) {
  const valueClasses = [styles.kpFieldValue];
  if (suffix) valueClasses.push(styles.kpFieldValueWithSuffix);
  if (tall) valueClasses.push(styles.kpFieldValueTall);

  return (
    <div className={styles.kpField}>
      <div className={styles.kpFieldIco}>{icon}</div>
      <div className={styles.kpFieldLabel}>{label}</div>
      <div className={valueClasses.join(" ")}>
        {value || ""}
        {suffix ? <span className={styles.kpFieldSuffix}>{suffix}</span> : null}
      </div>
    </div>
  );
}

interface KpPage1Props {
  data: KpProposal;
}

export function KpPage1({ data }: KpPage1Props) {
  const subtitle = data.subtitle || BRANDING.defaultSubtitle;

  const items = data.items ?? [];
  // REQ-4.4: pad to a minimum of 5 rows to preserve visual rhythm.
  const padded: (typeof items[number] | null)[] = [];
  const totalRows = Math.max(5, items.length);
  for (let i = 0; i < totalRows; i++) {
    padded.push(items[i] ?? null);
  }

  const grandTotal = calcGrandTotal(items);
  const symbol = currencySymbol(data.currency);
  const grandTotalText = grandTotal > 0 ? `${fmtRu(grandTotal)} ${symbol}` : "";

  return (
    <div className={styles.kpPage}>
      {/* Header */}
      <div className={styles.kp1Head}>
        <div className={styles.kp1HeadBluebar} />
        <div className={styles.kp1HeadRedbar} />
        <div className={styles.kp1HeadLogo}>
          <MasterBearingMark />
        </div>
        <div className={styles.kp1HeadIllu}>
          <HeavyMachineryIllu />
        </div>
        <div className={styles.kp1Title}>
          <h1>
            КОММЕРЧЕСКОЕ
            <br />
            ПРЕДЛОЖЕНИЕ
          </h1>
          <div className={styles.kp1TitleSub}>{subtitle}</div>
          <div className={styles.kp1TitleUnderline} />
        </div>
      </div>

      {/* Body */}
      <div className={styles.kp1Body}>
        <div className={styles.kpSectionH}>
          <div className={styles.iconSq}>
            <ShieldDoc />
          </div>
          <div className={styles.label}>ИНФОРМАЦИЯ О ПРЕДЛОЖЕНИИ</div>
        </div>

        <div className={styles.kpInfoGrid}>
          <KpField icon={<UserBadge />} label="Поставщик:" value={data.supplier} />
          <KpField icon={<Doc />} label="Условия оплаты:" value={data.payment} />

          <KpField icon={<UserTie />} label="Менеджер отдела продаж:" value={data.manager} />
          <KpField icon={<Cal />} label="Дата предоставления:" value={data.date} />

          <KpField icon={<Phone />} label="Телефон:" value={data.phone} />
          <KpField icon={<Clock />} label="Срок поставки:" value={data.lead} />

          <KpField icon={<Mail />} label="E-mail:" value={data.email} />
          <KpField
            icon={<Ruble />}
            label="Сумма КП:"
            value={data.amount ? fmtRu(data.amount) : ""}
            suffix={headlineSuffix(data.currency)}
          />

          <KpField icon={<Pin />} label="Адрес поставки:" value={data.address} />
          <KpField icon={<Pkg />} label="Цена включает:" value={data.price_includes} tall />

          <KpField icon={<Truck />} label="Базис поставки:" value={data.basis} />
        </div>

        <div className={styles.kpSectionH} style={{ marginTop: 16 }}>
          <div className={styles.iconSq}>
            <List />
          </div>
          <div className={styles.label}>ПЕРЕЧЕНЬ ТЕХНИКИ И СТОИМОСТЬ</div>
        </div>

        <div className={styles.kpTable}>
          <div className={styles.kpTableHead}>
            <div>№</div>
            <div>Наименование техники</div>
            <div>Модель / Характеристики</div>
            <div className={styles.kpTableHeadRight}>Кол-во</div>
            <div className={styles.kpTableHeadRight}>Цена за ед., {symbol}</div>
            <div className={styles.kpTableHeadRight}>Сумма, {symbol}</div>
          </div>
          {padded.map((row, i) => {
            const rowTotal = row ? calcRowTotal(row) : null;
            return (
              <div className={styles.kpTableRow} key={i}>
                <div className={styles.kpTableCellCenter}>{row ? i + 1 : ""}</div>
                <div>{row?.name ?? ""}</div>
                <div>{row?.model ?? ""}</div>
                <div className={styles.kpTableCellNum}>{row?.qty ?? ""}</div>
                <div className={styles.kpTableCellNum}>
                  {row?.price ? fmtRu(row.price) : ""}
                </div>
                <div className={styles.kpTableCellNum}>
                  {rowTotal !== null ? fmtRu(rowTotal) : ""}
                </div>
              </div>
            );
          })}
          <div className={styles.kpTableTotal}>
            <div className={styles.kpTableTotalLabel}>ИТОГО:</div>
            <div className={styles.kpTableTotalValue}>{grandTotalText}</div>
          </div>
        </div>

        <div className={styles.kp1Notes}>
          <div className={styles.kp1NotesNotes}>
            <div className={styles.kp1NotesL}>
              Примечания / Дополнительная информация:
            </div>
            <div className={styles.kp1NotesBox}>{data.notes || ""}</div>
          </div>
          <div className={styles.kp1Sigs}>
            <div className={styles.kp1Sig}>
              <div className={styles.kp1SigLine} />
              <div className={styles.kp1SigCap}>Подпись</div>
            </div>
            <div className={styles.kp1Sig}>
              <div className={styles.kp1SigLine} />
              <div className={styles.kp1SigCap}>М.П.</div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer feature strip */}
      <div className={styles.kp1Foot}>
        <div className={styles.kp1FootRed} />
        <div className={styles.kp1FootItems}>
          <div className={styles.kp1FootItem}>
            <div className={styles.kp1FootItemIco}>
              <Shield />
            </div>
            <div className={styles.kp1FootItemTxt}>
              НАДЕЖНЫЕ
              <br />
              ПОСТАВКИ
            </div>
          </div>
          <div className={styles.kp1FootItem}>
            <div className={styles.kp1FootItemIco}>
              <ShieldCheck />
            </div>
            <div className={styles.kp1FootItemTxt}>
              КАЧЕСТВЕННАЯ
              <br />
              ПРОДУКЦИЯ
            </div>
          </div>
          <div className={styles.kp1FootItem}>
            <div className={styles.kp1FootItemIco}>
              <Cog />
            </div>
            <div className={styles.kp1FootItemTxt}>
              ТЕХНИЧЕСКАЯ
              <br />
              ПОДДЕРЖКА
            </div>
          </div>
          <div className={styles.kp1FootItem}>
            <div className={styles.kp1FootItemIco}>
              <Handshake />
            </div>
            <div className={styles.kp1FootItemTxt}>
              ИНДИВИДУАЛЬНЫЙ
              <br />
              ПОДХОД
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
