import type { KpProposal } from "./types";

/**
 * Default example proposal — Master Bearing heavy machinery.
 *
 * Mirrors `tests/services/__fixtures__/default_proposal.json` field-for-field
 * (snake_case keys, padded specs/packaging arrays). The Python visual
 * regression baseline is generated from the same fixture, so any drift here
 * must be matched on the backend or it breaks the regression test.
 *
 * Used by:
 * - `useKpState` first-time hydration (REQ-2.1)
 * - "Пример" button action (REQ-2.5)
 */
export const DEFAULT_PROPOSAL: KpProposal = {
  subtitle: "на поставку крупной спецтехники",
  supplier: "ООО «Мастер Беринг»",
  manager: "Соколов А. В.",
  phone: "+7 (495) 120-45-67",
  email: "sokolov@masterbearing.ru",
  address: "г. Москва, Складской комплекс «ЮгТранс»",
  basis: "DDP — склад покупателя",
  payment: "50% предоплата / 50% по факту поставки",
  date: "21.05.2026",
  lead: "60 рабочих дней",
  amount: "12 480 000",
  price_includes:
    "Доставка до склада покупателя, НДС 20%, заводская упаковка, ввод в эксплуатацию.",
  items: [
    {
      name: "Бульдозер гусеничный",
      model: "Shantui SD16, 162 л.с., отвал 3,4 м³",
      qty: "1",
      price: "5 850 000",
    },
    {
      name: "Экскаватор гусеничный",
      model: "SANY SY215C, 21 т, ковш 1,1 м³",
      qty: "1",
      price: "6 630 000",
    },
    { name: "", model: "", qty: "", price: "" },
  ],
  notes:
    "Предложение действительно 14 календарных дней с даты предоставления. Цены указаны для условий, согласованных при подписании счёта.",
  specs: [
    "Мощность двигателя — от 162 до 215 л.с.",
    "Эксплуатационная масса — 17,2 — 21,5 т",
    "Объём ковша / отвала — 1,1 — 3,4 м³",
    "Расход топлива — до 28 л/час",
    "Тип трансмиссии — гидростатическая",
    "Климатическое исполнение — УХЛ-1",
    "",
    "",
  ],
  packaging: [
    { text: "Кабина ROPS/FOPS с кондиционером", checked: true },
    { text: "Гидростатическая трансмиссия", checked: true },
    { text: "Комплект инструмента и ЗИП", checked: true },
    { text: "Подогрев двигателя 220 В", checked: false },
    { text: "Камеры заднего вида", checked: true },
    { text: "Антивандальная защита фар", checked: false },
    { text: "Сертификат ЕАЭС", checked: true },
    { text: "", checked: false },
  ],
  conditions: [
    "Гарантия — 12 месяцев или 2 000 моточасов (что наступит раньше)",
    "Бесплатное ТО-0 и ТО-1 силами сервисной службы поставщика",
    "Поставка ЗИП и расходных материалов со склада в Москве",
  ],
  services: {
    delivery: true,
    training: true,
    supervision: false,
    warranty: false,
    commissioning: true,
    service: false,
  },
  notes2: "",
  contact_phone: "+7 (495) 120-45-67",
  contact_email: "sokolov@masterbearing.ru",
  contact_site: "www.masterbearing.ru",
  contact_address: "г. Москва, ул. Большая Семёновская, 40",
  foot_phone: "8-800-350-21-34",
  foot_site: "www.masterbearing.ru",
  foot_email: "order@masterbearing.ru",
  currency: "RUB",
};
