/**
 * prototype/seed.js — in-memory mock data for prototype.html.
 *
 * Mirrors the TS types from entities/* so Round 5-7 split is mechanical:
 *   - WorkspaceInvoiceRow  → entities/workspace-invoice/queries.ts
 *   - LogisticsSegment     → entities/logistics-segment/queries.ts
 *   - LogisticsTemplate    → entities/logistics-template/queries.ts
 *   - LocationOption       → entities/location/queries.ts
 *   - RoutingPattern       → (admin-routing-logistics / spec §13)
 *
 * Two flavours:
 *   SEED_NORMAL      — healthy org: green SLAs, everything assigned, no review flags
 *   SEED_EDGE_CASES  — stressed org: overdue SLAs, 3 unassigned, 2 needs_review, coverage gap
 *
 * Exposed on window for babel-script sharing (same-scope caveat, see CLAUDE.md).
 */

// ----- Reference data (shared between both seed sets) -----

const USERS = [
  { id: "u-head-log", name: "Марина Коваль", email: "kovak@onestack.ru", roles: ["head_of_logistics", "logistics"] },
  { id: "u-log-1",   name: "Денис Орлов",   email: "orlov@onestack.ru",  roles: ["logistics"] },
  { id: "u-log-2",   name: "Илья Басов",    email: "basov@onestack.ru",  roles: ["logistics"] },
  { id: "u-log-3",   name: "Света Рей",     email: "rey@onestack.ru",    roles: ["logistics"] },
  { id: "u-head-cus", name: "Пётр Лыков",   email: "lykov@onestack.ru",  roles: ["head_of_customs", "customs"] },
  { id: "u-cus-1",   name: "Анна Гром",     email: "grom@onestack.ru",   roles: ["customs"] },
  { id: "u-cus-2",   name: "Роман Куц",     email: "kuts@onestack.ru",   roles: ["customs"] },
  { id: "u-admin",   name: "Игорь Демин",   email: "demin@onestack.ru",  roles: ["admin"] },
  { id: "u-both",    name: "Ольга Титова",  email: "titova@onestack.ru", roles: ["head_of_logistics", "head_of_customs"] },
];

const LOCATIONS = [
  { id: "loc-shanghai",      country: "Китай",    iso2: "cn", city: "Шанхай",          type: "supplier" },
  { id: "loc-guangzhou",     country: "Китай",    iso2: "cn", city: "Гуанчжоу",        type: "supplier" },
  { id: "loc-istanbul-fact", country: "Турция",   iso2: "tr", city: "Стамбул (фабрика)", type: "supplier" },
  { id: "loc-sklad-sh",      country: "Китай",    iso2: "cn", city: "Склад в Шанхае",  type: "hub" },
  { id: "loc-sklad-ist",     country: "Турция",   iso2: "tr", city: "Склад Стамбул",   type: "hub" },
  { id: "loc-tamojnja-msk",  country: "Россия",   iso2: "ru", city: "Таможня Москва",  type: "customs" },
  { id: "loc-tamojnja-spb",  country: "Россия",   iso2: "ru", city: "Таможня СПб",     type: "customs" },
  { id: "loc-wh-msk",        country: "Россия",   iso2: "ru", city: "Склад Москва",    type: "own_warehouse" },
  { id: "loc-client-ekb",    country: "Россия",   iso2: "ru", city: "Екатеринбург",    type: "client" },
  { id: "loc-client-nsk",    country: "Россия",   iso2: "ru", city: "Новосибирск",     type: "client" },
  { id: "loc-client-kzn",    country: "Россия",   iso2: "ru", city: "Казань",          type: "client" },
];

const TEMPLATES = [
  {
    id: "tpl-china-msk",
    name: "Китай → Москва (стандарт)",
    description: "Типовой маршрут через московскую таможню",
    segments: [
      { id: "ts-1a", sequenceOrder: 1, fromLocationType: "supplier", toLocationType: "hub",           defaultLabel: "First mile",    defaultDays: 3  },
      { id: "ts-1b", sequenceOrder: 2, fromLocationType: "hub",      toLocationType: "customs",       defaultLabel: "Main freight", defaultDays: 28 },
      { id: "ts-1c", sequenceOrder: 3, fromLocationType: "customs",  toLocationType: "own_warehouse", defaultLabel: "ГТД → склад", defaultDays: 2  },
      { id: "ts-1d", sequenceOrder: 4, fromLocationType: "own_warehouse", toLocationType: "client",   defaultLabel: "Last mile",    defaultDays: 3  },
    ],
  },
  {
    id: "tpl-turkey-msk",
    name: "Турция → Москва (авто)",
    description: "Автомобильный трафик из Стамбула",
    segments: [
      { id: "ts-2a", sequenceOrder: 1, fromLocationType: "supplier", toLocationType: "customs", defaultLabel: "Straight haul",  defaultDays: 12 },
      { id: "ts-2b", sequenceOrder: 2, fromLocationType: "customs",  toLocationType: "client",  defaultLabel: "Customs → client", defaultDays: 2 },
    ],
  },
  {
    id: "tpl-express",
    name: "Экспресс через СПб",
    description: "Быстрый маршрут для срочных заказов",
    segments: [
      { id: "ts-3a", sequenceOrder: 1, fromLocationType: "supplier", toLocationType: "customs", defaultLabel: "Air/express",  defaultDays: 4 },
      { id: "ts-3b", sequenceOrder: 2, fromLocationType: "customs",  toLocationType: "client",  defaultLabel: "Delivery",     defaultDays: 1 },
    ],
  },
];

// ----- Helpers -----

const HOUR = 60 * 60 * 1000;
const now = () => Date.now();
const iso = (ms) => new Date(ms).toISOString();

function mkAssignment({ assignedAt, slaHours, completedAt, user }) {
  return {
    assigned_user: user ?? null,
    assigned_at: assignedAt != null ? iso(assignedAt) : null,
    deadline_at: assignedAt != null && slaHours != null ? iso(assignedAt + slaHours * HOUR) : null,
    completed_at: completedAt != null ? iso(completedAt) : null,
    sla_hours: slaHours ?? 72,
  };
}

// ----- SEED NORMAL -----

function makeSeedNormal() {
  const t = now();

  const invoices = [
    {
      id: "inv-1001",
      quote_id: "q-2104-018",
      idn_quote: "Q-210418",
      customer: { id: "c-1", name: "ООО Лего Плюс", city: "Екатеринбург" },
      pickup: { country: "Китай",  iso2: "cn", city: "Шанхай" },
      delivery: { country: "Россия", iso2: "ru", city: "Екатеринбург" },
      supplier_name: "Shanghai Industrial",
      items_count: 12, total_weight_kg: 840, total_volume_m3: 5.2, packages_count: 24,
      hs_codes_filled: 0, hs_codes_total: 12,
      licenses_required: false,
      logistics: mkAssignment({ assignedAt: t - 14 * HOUR, slaHours: 72, user: "u-log-1" }),
      customs:   mkAssignment({ assignedAt: t - 14 * HOUR, slaHours: 72, user: "u-cus-1" }),
    },
    {
      id: "inv-1002",
      quote_id: "q-2104-019",
      idn_quote: "Q-210419",
      customer: { id: "c-2", name: "Торговый Дом Премиум", city: "Москва" },
      pickup: { country: "Турция", iso2: "tr", city: "Стамбул" },
      delivery: { country: "Россия", iso2: "ru", city: "Москва" },
      supplier_name: "Istanbul Textile Co",
      items_count: 28, total_weight_kg: 1250, total_volume_m3: 9.8, packages_count: 41,
      hs_codes_filled: 5, hs_codes_total: 28,
      licenses_required: true,
      logistics: mkAssignment({ assignedAt: t - 40 * HOUR, slaHours: 72, user: "u-log-2" }),
      customs:   mkAssignment({ assignedAt: t - 40 * HOUR, slaHours: 72, user: "u-cus-2" }),
    },
    {
      id: "inv-1003",
      quote_id: "q-2104-020",
      idn_quote: "Q-210420",
      customer: { id: "c-3", name: "Сибирь Маркет", city: "Новосибирск" },
      pickup: { country: "Китай", iso2: "cn", city: "Гуанчжоу" },
      delivery: { country: "Россия", iso2: "ru", city: "Новосибирск" },
      supplier_name: "Guangzhou Foshan Ltd",
      items_count: 7, total_weight_kg: 320, total_volume_m3: 2.1, packages_count: 10,
      hs_codes_filled: 7, hs_codes_total: 7,
      licenses_required: false,
      logistics: mkAssignment({ assignedAt: t - 52 * HOUR, slaHours: 72, completedAt: t - 2 * HOUR, user: "u-log-1" }),
      customs:   mkAssignment({ assignedAt: t - 52 * HOUR, slaHours: 72, user: "u-cus-1" }),
    },
    {
      id: "inv-1004",
      quote_id: "q-2104-021",
      idn_quote: "Q-210421",
      customer: { id: "c-4", name: "Казань Маркет", city: "Казань" },
      pickup: { country: "Китай", iso2: "cn", city: "Шанхай" },
      delivery: { country: "Россия", iso2: "ru", city: "Казань" },
      supplier_name: "Shanghai Industrial",
      items_count: 16, total_weight_kg: 980, total_volume_m3: 6.4, packages_count: 31,
      hs_codes_filled: 16, hs_codes_total: 16,
      licenses_required: true,
      logistics: mkAssignment({ assignedAt: t - 70 * HOUR, slaHours: 72, completedAt: t - 6 * HOUR, user: "u-log-3" }),
      customs:   mkAssignment({ assignedAt: t - 70 * HOUR, slaHours: 72, completedAt: t - 1 * HOUR, user: "u-cus-2" }),
    },
    {
      id: "inv-1005",
      quote_id: "q-2104-022",
      idn_quote: "Q-210422",
      customer: { id: "c-5", name: "АзияИмпорт", city: "Москва" },
      pickup: { country: "Китай", iso2: "cn", city: "Шанхай" },
      delivery: { country: "Россия", iso2: "ru", city: "Москва" },
      supplier_name: "Shanghai Industrial",
      items_count: 9, total_weight_kg: 560, total_volume_m3: 3.4, packages_count: 15,
      hs_codes_filled: 9, hs_codes_total: 9,
      licenses_required: false,
      logistics: mkAssignment({ assignedAt: t - 80 * HOUR, slaHours: 72, completedAt: t - 10 * HOUR, user: "u-log-2" }),
      customs:   mkAssignment({ assignedAt: t - 80 * HOUR, slaHours: 72, completedAt: t - 4 * HOUR, user: "u-cus-1" }),
    },
    {
      id: "inv-1006",
      quote_id: "q-2104-023",
      idn_quote: "Q-210423",
      customer: { id: "c-2", name: "Торговый Дом Премиум", city: "Москва" },
      pickup: { country: "Турция", iso2: "tr", city: "Стамбул" },
      delivery: { country: "Россия", iso2: "ru", city: "Москва" },
      supplier_name: "Ankara Light",
      items_count: 22, total_weight_kg: 1420, total_volume_m3: 11.1, packages_count: 38,
      hs_codes_filled: 0, hs_codes_total: 22,
      licenses_required: false,
      logistics: mkAssignment({ assignedAt: t - 6 * HOUR, slaHours: 72, user: "u-log-2" }),
      customs:   mkAssignment({ assignedAt: t - 6 * HOUR, slaHours: 72, user: "u-cus-2" }),
    },
  ];

  return { users: USERS, locations: LOCATIONS, templates: TEMPLATES, invoices, unassigned: [], routing_patterns: makePatternsNormal(), coverage_gaps: [] };
}

function makePatternsNormal() {
  return [
    { id: "rp-1", origin_country: "Китай",  origin_iso2: "cn", dest_city: "*",              dest_iso2: null, assignee: "u-log-1", specificity: "wildcard", usage_month: 14 },
    { id: "rp-2", origin_country: "Турция", origin_iso2: "tr", dest_city: "*",              dest_iso2: null, assignee: "u-log-2", specificity: "wildcard", usage_month: 8  },
    { id: "rp-3", origin_country: "Китай",  origin_iso2: "cn", dest_city: "Екатеринбург",   dest_iso2: "ru", assignee: "u-log-3", specificity: "exact",    usage_month: 3  },
    { id: "rp-4", origin_country: "*",      origin_iso2: null, dest_city: "*",              dest_iso2: null, assignee: "u-head-log", specificity: "wildcard", usage_month: 0 },
  ];
}

// ----- SEED EDGE CASES -----

function makeSeedEdgeCases() {
  const base = makeSeedNormal();
  const t = now();

  // Overdue + needs_review on inv-1001
  base.invoices[0].logistics = mkAssignment({ assignedAt: t - 80 * HOUR, slaHours: 72, user: "u-log-1" }); // overdue
  base.invoices[0].logistics_needs_review_since = iso(t - 2 * HOUR);
  base.invoices[0].review_diff = { weight: { old: 840, new: 1150 } };

  // Nearly-overdue on inv-1002 (15h left)
  base.invoices[1].logistics = mkAssignment({ assignedAt: t - 57 * HOUR, slaHours: 72, user: "u-log-2" });

  // 3 unassigned (no pattern match)
  base.unassigned = [
    {
      id: "inv-u01",
      quote_id: "q-2104-030",
      idn_quote: "Q-210430",
      customer: { id: "c-6", name: "ВьетИмпорт",  city: "Москва" },
      pickup: { country: "Вьетнам",   iso2: "vn", city: "Хошимин" },
      delivery: { country: "Россия",   iso2: "ru", city: "Москва" },
      supplier_name: "Saigon Textiles",
      items_count: 5, total_weight_kg: 220, total_volume_m3: 1.6, packages_count: 8,
      hs_codes_filled: 0, hs_codes_total: 5, licenses_required: false,
      stuck_for_hours: 3,
    },
    {
      id: "inv-u02",
      quote_id: "q-2104-031",
      idn_quote: "Q-210431",
      customer: { id: "c-7", name: "Глобал Трейд", city: "Казань" },
      pickup: { country: "Индия",     iso2: "in", city: "Мумбаи" },
      delivery: { country: "Россия",   iso2: "ru", city: "Казань" },
      supplier_name: "Mumbai Exports",
      items_count: 14, total_weight_kg: 780, total_volume_m3: 5.0, packages_count: 22,
      hs_codes_filled: 0, hs_codes_total: 14, licenses_required: true,
      stuck_for_hours: 8,
    },
    {
      id: "inv-u03",
      quote_id: "q-2104-032",
      idn_quote: "Q-210432",
      customer: { id: "c-8", name: "Южный Груз",  city: "Новосибирск" },
      pickup: { country: "Вьетнам",   iso2: "vn", city: "Ханой" },
      delivery: { country: "Россия",   iso2: "ru", city: "Новосибирск" },
      supplier_name: "Hanoi Goods",
      items_count: 9, total_weight_kg: 410, total_volume_m3: 2.9, packages_count: 14,
      hs_codes_filled: 0, hs_codes_total: 9, licenses_required: false,
      stuck_for_hours: 14,
    },
  ];

  base.coverage_gaps = [
    { country: "Вьетнам",   iso2: "vn", stuck_count: 2 },
    { country: "Индия",     iso2: "in", stuck_count: 1 },
  ];

  return base;
}

// ----- Segments for the active quote (used by Route Constructor) -----

function makeSegmentsForInvoice(invoiceId) {
  if (invoiceId === "inv-1001") {
    return [
      { id: "seg-a1", invoiceId, sequenceOrder: 1, fromLocation: byId("loc-shanghai"),    toLocation: byId("loc-sklad-sh"),      label: "First mile",    transitDays: 3,  mainCostRub:  45000, carrier: "SF Express",            notes: "", expenses: [{ id: "e-1", label: "Упаковка", costRub: 3500, days: 0 }] },
      { id: "seg-a2", invoiceId, sequenceOrder: 2, fromLocation: byId("loc-sklad-sh"),    toLocation: byId("loc-tamojnja-msk"),  label: "Main freight",  transitDays: 28, mainCostRub: 380000, carrier: "COSCO",                 notes: "Контейнер 40HQ", expenses: [{ id: "e-2", label: "СВХ Москва", costRub: 12000, days: 2 }] },
      { id: "seg-a3", invoiceId, sequenceOrder: 3, fromLocation: byId("loc-tamojnja-msk"),toLocation: byId("loc-wh-msk"),        label: "ГТД → склад",   transitDays: 2,  mainCostRub:  18000, carrier: "Деловые Линии",         notes: "", expenses: [] },
      { id: "seg-a4", invoiceId, sequenceOrder: 4, fromLocation: byId("loc-wh-msk"),      toLocation: byId("loc-client-ekb"),    label: "Last mile",     transitDays: 4,  mainCostRub:  35000, carrier: "ПЭК",                   notes: "Разгрузка утром", expenses: [] },
    ];
  }
  if (invoiceId === "inv-1002") {
    return [
      { id: "seg-b1", invoiceId, sequenceOrder: 1, fromLocation: byId("loc-istanbul-fact"), toLocation: byId("loc-tamojnja-msk"), label: "Straight haul",    transitDays: 12, mainCostRub: 210000, carrier: "Ankara Logistics", notes: "", expenses: [{ id: "e-3", label: "Страховка", costRub: 8500 }] },
      { id: "seg-b2", invoiceId, sequenceOrder: 2, fromLocation: byId("loc-tamojnja-msk"),  toLocation: byId("loc-client-ekb"),   label: "Customs → client", transitDays: 2,  mainCostRub:  22000, carrier: "ПЭК",              notes: "", expenses: [] },
    ];
  }
  return [];
}
function byId(id) { return LOCATIONS.find((l) => l.id === id); }

// ----- Customs items for the active quote (used by Customs rails table) -----

function makeCustomsItems() {
  return [
    { id: "ci-1", brand: "Lumina", product_code: "LM-2204-A", product_name: "Настольная лампа",             qty: 120, weight_kg: 84,   hs_code: "9405.20.40",  duty_pct: 7.5,  duty_per_kg: null, vat_pct: 20, license_ds: true,  license_ss: false, license_sgr: false, honest_mark: false, autofill: { source: "Q-202511-017", date: "2025-11-14" } },
    { id: "ci-2", brand: "Lumina", product_code: "LM-2204-B", product_name: "Настольная лампа XL",          qty:  60, weight_kg: 72,   hs_code: "9405.20.40",  duty_pct: 7.5,  duty_per_kg: null, vat_pct: 20, license_ds: true,  license_ss: false, license_sgr: false, honest_mark: false, autofill: { source: "Q-202511-017", date: "2025-11-14" } },
    { id: "ci-3", brand: "TexWare", product_code: "TW-0391",  product_name: "Полотенце банное 70×140",      qty: 400, weight_kg: 160,  hs_code: "6302.60.00",  duty_pct: 8.0,  duty_per_kg: null, vat_pct: 20, license_ds: false, license_ss: true,  license_sgr: false, honest_mark: true,  autofill: { source: "Q-202602-004", date: "2026-02-19" } },
    { id: "ci-4", brand: "TexWare", product_code: "TW-0519",  product_name: "Простыня 200×220",             qty: 200, weight_kg: 120,  hs_code: null,          duty_pct: null, duty_per_kg: null, vat_pct: null, license_ds: false, license_ss: false, license_sgr: false, honest_mark: false, autofill: null },
    { id: "ci-5", brand: "GreenLeaf", product_code: "GL-KT7", product_name: "Кашпо керамическое 30 см",     qty:  80, weight_kg: 240,  hs_code: "6914.10.00",  duty_pct: 10,   duty_per_kg: null, vat_pct: 20, license_ds: false, license_ss: false, license_sgr: false, honest_mark: false, autofill: { source: "Q-202603-012", date: "2026-03-05" } },
    { id: "ci-6", brand: "GreenLeaf", product_code: "GL-KT9", product_name: "Кашпо керамическое 40 см",     qty:  40, weight_kg: 160,  hs_code: null,          duty_pct: null, duty_per_kg: null, vat_pct: null, license_ds: false, license_ss: false, license_sgr: false, honest_mark: false, autofill: null },
    { id: "ci-7", brand: "Nova",   product_code: "NV-FT3",   product_name: "Фильтр для воды, картридж",     qty: 300, weight_kg:  45,  hs_code: "8421.21.00",  duty_pct: null, duty_per_kg: 12,   vat_pct: 20, license_ds: true,  license_ss: true,  license_sgr: true,  honest_mark: false, autofill: { source: "Q-202601-022", date: "2026-01-30" } },
  ];
}

// ----- Export -----

window.__SEED__ = {
  normal: makeSeedNormal,
  edgeCases: makeSeedEdgeCases,
  segmentsForInvoice: makeSegmentsForInvoice,
  customsItems: makeCustomsItems,
  byId,
};
