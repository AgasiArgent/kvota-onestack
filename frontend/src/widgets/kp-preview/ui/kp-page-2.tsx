/**
 * Page 2 of the КП preview — header strip with 2/2 badge, two-column
 * specs+packaging cards, conditions section, six service indicators,
 * notes-2 box, contacts panel with mountains illustration, page-2 footer.
 *
 * Mirrors `KpPage2.jsx` from the design prototype. Service labels are in
 * the fixed Russian order from REQ-9.3.
 */

import { BRANDING } from "@/entities/kp-proposal";
import type { KpPackagingItem, KpProposal } from "@/entities/kp-proposal";

import {
  Clock,
  Cog,
  Gear,
  Globe,
  Mail,
  Phone,
  Pin,
  Settings,
  Shield,
  ShieldCheck,
  Tools,
  Truck,
  UserBadge,
  Wrench,
} from "./icons";
import { MountainIllu } from "./illustrations";
import styles from "./kp-preview.module.css";
import { MasterBearingMark } from "./master-bearing-mark";

const SERVICE_ROWS: ReadonlyArray<{
  key: keyof KpProposal["services"];
  icon: React.ComponentType;
  label: string;
}> = [
  { key: "delivery", icon: Truck, label: "Доставка" },
  { key: "training", icon: UserBadge, label: "Обучение операторов" },
  { key: "supervision", icon: Wrench, label: "Шеф-монтаж" },
  { key: "warranty", icon: ShieldCheck, label: "Расширенная гарантия" },
  { key: "commissioning", icon: Cog, label: "Пусконаладочные работы" },
  { key: "service", icon: Settings, label: "Сервисное обслуживание" },
];

interface KpPage2Props {
  data: KpProposal;
}

export function KpPage2({ data }: KpPage2Props) {
  const subtitle = data.subtitle || BRANDING.defaultSubtitle;

  // REQ-6.3 / 7.4 / 8.3: pad lists to preserve layout balance.
  const specsPadded = padStrings(data.specs ?? [], 8);
  const pkgPadded = padPackaging(data.packaging ?? [], 8);
  const conditionsPadded = padStrings(data.conditions ?? [], 3);

  return (
    <div className={styles.kpPage}>
      {/* Header — mirrors page 1's blue+red slash geometry */}
      <div className={styles.kp2Head}>
        <div className={styles.kp2HeadBluebar} />
        <div className={styles.kp2HeadRedbar} />
        <div className={styles.kp2HeadLogo}>
          <MasterBearingMark />
        </div>
        <div className={styles.kp2HeadTitle}>
          <h2>КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ</h2>
          <div className={styles.kp2HeadTitleSub}>{subtitle}</div>
        </div>
        <div className={styles.kp2HeadPageno}>2/2</div>
      </div>

      {/* Body */}
      <div className={styles.kp2Body}>
        <div className={styles.kpSectionH} style={{ margin: 0 }}>
          <div className={styles.iconSq}>
            <Settings />
          </div>
          <div className={styles.label}>
            ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ И КОМПЛЕКТАЦИЯ
          </div>
        </div>

        {/* Two cards: specs + packaging */}
        <div className={styles.kp2Twocol}>
          <div className={styles.kpBlock}>
            <div className={styles.kpBlockHead}>
              <Gear />
              <span>ОСНОВНЫЕ ХАРАКТЕРИСТИКИ</span>
            </div>
            <div className={styles.kpBlockBody}>
              <div className={styles.kpBulletList}>
                {specsPadded.map((s, i) => (
                  <div className={styles.item} key={i}>
                    <div className={styles.b} />
                    <div className={styles.v}>{s}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className={styles.kpBlock}>
            <div className={styles.kpBlockHead}>
              <Clock />
              <span>КОМПЛЕКТАЦИЯ</span>
            </div>
            <div className={styles.kpBlockBody}>
              <div className={styles.kpCheckList}>
                {pkgPadded.map((p, i) => (
                  <div className={styles.item} key={i}>
                    <div
                      className={`${styles.c} ${p.checked ? styles.checked : ""}`}
                    />
                    <div className={styles.v}>{p.text}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Conditions */}
        <div>
          <div className={styles.kpSectionH} style={{ margin: "4px 0 8px" }}>
            <div className={styles.iconSq}>
              <Shield />
            </div>
            <div className={styles.label}>УСЛОВИЯ И ГАРАНТИИ</div>
          </div>
          <div className={styles.kpConditions}>
            {conditionsPadded.map((c, i) => (
              <div className={styles.row} key={i}>
                <div className={styles.b} />
                <div className={styles.v}>{c}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Services + notes-2 */}
        <div className={styles.kp2Services}>
          <div className={styles.kpServices}>
            <div className={styles.kpServicesHead}>
              <div className={styles.ico}>
                <Tools />
              </div>
              <span>ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ</span>
              <span className={styles.req}>(по запросу)</span>
            </div>
            <div className={styles.kpServicesGrid}>
              {SERVICE_ROWS.map(({ key, icon: Icon, label }) => (
                <div className={styles.kpServicesItem} key={key}>
                  <div className={styles.ico}>
                    <Icon />
                  </div>
                  <div>{label}</div>
                  <div
                    className={`${styles.c} ${
                      data.services[key] ? styles.checked : ""
                    }`}
                  />
                </div>
              ))}
            </div>
          </div>
          <div className={styles.kpNotesBox}>
            <div className={styles.kpNotesBoxHead}>ДЛЯ ЗАМЕТОК</div>
            <div className={styles.kpNotesBoxBody}>{data.notes2 || ""}</div>
          </div>
        </div>

        {/* Contacts + thanks */}
        <div className={styles.kp2Contacts}>
          <div className={styles.kpContacts}>
            <div className={styles.kpContactsHead}>КОНТАКТЫ</div>
            <div className={styles.kpContactsRow}>
              <div className={styles.ico}>
                <Phone />
              </div>
              <div className={styles.l}>Телефон:</div>
              <div className={styles.v}>{data.contact_phone || ""}</div>
            </div>
            <div className={styles.kpContactsRow}>
              <div className={styles.ico}>
                <Mail />
              </div>
              <div className={styles.l}>E-mail:</div>
              <div className={styles.v}>{data.contact_email || ""}</div>
            </div>
            <div className={styles.kpContactsRow}>
              <div className={styles.ico}>
                <Globe />
              </div>
              <div className={styles.l}>Сайт:</div>
              <div className={styles.v}>{data.contact_site || ""}</div>
            </div>
            <div className={styles.kpContactsRow}>
              <div className={styles.ico}>
                <Pin />
              </div>
              <div className={styles.l}>Адрес:</div>
              <div className={styles.v}>{data.contact_address || ""}</div>
            </div>
          </div>
          <div className={styles.kpThanks}>
            <div className={styles.kpThanksText}>
              Благодарим за обращение!
              <br />
              Будем рады сотрудничеству.
            </div>
            <div className={styles.kpThanksMtn}>
              <MountainIllu />
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className={styles.kp2Foot}>
        <div className={styles.kp2FootRed} />
        <div className={styles.kp2FootItems}>
          <div className={styles.kp2FootItem}>
            <div className={styles.kp2FootItemIco}>
              <Phone />
            </div>
            <span>{data.foot_phone || BRANDING.footPhone}</span>
          </div>
          <div className={styles.kp2FootItem}>
            <div className={styles.kp2FootItemIco}>
              <Globe />
            </div>
            <span>{data.foot_site || BRANDING.footSite}</span>
          </div>
          <div className={styles.kp2FootItem}>
            <div className={styles.kp2FootItemIco}>
              <Mail />
            </div>
            <span>{data.foot_email || BRANDING.footEmail}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function padStrings(values: string[], min: number): string[] {
  if (values.length >= min) return values;
  return [...values, ...new Array(min - values.length).fill("")];
}

function padPackaging(values: KpPackagingItem[], min: number): KpPackagingItem[] {
  if (values.length >= min) return values;
  const filler: KpPackagingItem[] = new Array(min - values.length).fill(null).map(
    () => ({ text: "", checked: false }),
  );
  return [...values, ...filler];
}
