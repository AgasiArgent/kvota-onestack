import {
  Document,
  Page,
  View,
  Text,
  Image,
  StyleSheet,
  Font,
} from "@react-pdf/renderer";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Font registration (Roboto — good Cyrillic support, similar to Manrope)
// ---------------------------------------------------------------------------

Font.register({
  family: "Roboto",
  fonts: [
    {
      src: "https://fonts.gstatic.com/s/roboto/v47/KFOMCnqEu92Fr1ME7kSn66aGLdTylUAMQXC89YmC2DPNWubEbGmT.ttf",
      fontWeight: 400,
    },
    {
      src: "https://fonts.gstatic.com/s/roboto/v47/KFOMCnqEu92Fr1ME7kSn66aGLdTylUAMQXC89YmC2DPNWuaabWmT.ttf",
      fontWeight: 700,
    },
  ],
});

// ---------------------------------------------------------------------------
// Brand colors
// ---------------------------------------------------------------------------

const NAVY = "#005BAA";
const DARK_TEXT = "#161616";
const LIGHT_BG = "#F0F2F3";
const WHITE = "#FFFFFF";
const GRAY_TEXT = "#555555";
const TABLE_ALT = "#F7F8F9";
const BORDER_COLOR = "#D1D5DB";

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const s = StyleSheet.create({
  page: {
    fontFamily: "Roboto",
    fontSize: 9,
    color: DARK_TEXT,
    paddingTop: 0,
    paddingBottom: 50,
    paddingHorizontal: 0,
  },

  // Header band
  headerBand: {
    backgroundColor: NAVY,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 30,
    paddingVertical: 14,
  },
  logo: {
    height: 44,
    width: 140,
    objectFit: "contain",
  },
  headerTitle: {
    color: WHITE,
    fontSize: 16,
    fontWeight: 700,
    letterSpacing: 1,
  },

  // Body content padding
  body: {
    paddingHorizontal: 30,
  },

  // Quote number
  quoteNumber: {
    fontSize: 11,
    fontWeight: 700,
    marginTop: 14,
    marginBottom: 10,
  },

  // Two-column info block
  infoRow: {
    flexDirection: "row",
    gap: 16,
    marginBottom: 12,
  },
  infoCol: {
    flex: 1,
    padding: 10,
    borderWidth: 1,
    borderColor: BORDER_COLOR,
    borderRadius: 3,
  },
  infoTitle: {
    fontSize: 8,
    fontWeight: 700,
    color: NAVY,
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  infoLine: {
    fontSize: 8.5,
    marginBottom: 2.5,
    color: DARK_TEXT,
  },
  infoLabel: {
    color: GRAY_TEXT,
  },

  // Supplier block
  supplierBlock: {
    backgroundColor: LIGHT_BG,
    padding: 10,
    borderRadius: 3,
    marginBottom: 12,
  },

  // Summary cards
  summaryRow: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 14,
  },
  summaryCard: {
    flex: 1,
    padding: 10,
    borderWidth: 1,
    borderColor: BORDER_COLOR,
    borderRadius: 3,
    alignItems: "center",
  },
  summaryCardAccent: {
    flex: 1,
    padding: 10,
    borderRadius: 3,
    backgroundColor: NAVY,
    alignItems: "center",
  },
  summaryLabel: {
    fontSize: 7.5,
    color: GRAY_TEXT,
    marginBottom: 3,
    textTransform: "uppercase",
  },
  summaryLabelAccent: {
    fontSize: 7.5,
    color: "rgba(255,255,255,0.8)",
    marginBottom: 3,
    textTransform: "uppercase",
  },
  summaryValue: {
    fontSize: 12,
    fontWeight: 700,
  },
  summaryValueAccent: {
    fontSize: 12,
    fontWeight: 700,
    color: WHITE,
  },

  // Table
  table: {
    marginBottom: 10,
  },
  tableHeader: {
    flexDirection: "row",
    backgroundColor: NAVY,
    paddingVertical: 5,
    paddingHorizontal: 2,
  },
  tableHeaderCell: {
    color: WHITE,
    fontSize: 6.5,
    fontWeight: 700,
    textAlign: "center",
    paddingHorizontal: 2,
  },
  tableRow: {
    flexDirection: "row",
    paddingVertical: 4,
    paddingHorizontal: 2,
    borderBottomWidth: 0.5,
    borderBottomColor: BORDER_COLOR,
  },
  tableRowAlt: {
    flexDirection: "row",
    paddingVertical: 4,
    paddingHorizontal: 2,
    backgroundColor: TABLE_ALT,
    borderBottomWidth: 0.5,
    borderBottomColor: BORDER_COLOR,
  },
  tableCell: {
    fontSize: 7.5,
    textAlign: "center",
    paddingHorizontal: 2,
  },
  tableCellLeft: {
    fontSize: 7.5,
    textAlign: "left",
    paddingHorizontal: 2,
  },
  tableTotalRow: {
    flexDirection: "row",
    paddingVertical: 5,
    paddingHorizontal: 2,
    borderTopWidth: 1.5,
    borderTopColor: NAVY,
  },
  tableTotalCell: {
    fontSize: 8.5,
    fontWeight: 700,
    textAlign: "center",
    paddingHorizontal: 2,
  },
  tableTotalCellLeft: {
    fontSize: 8.5,
    fontWeight: 700,
    textAlign: "left",
    paddingHorizontal: 2,
  },

  // Validity
  validity: {
    fontSize: 8.5,
    color: GRAY_TEXT,
    marginTop: 6,
    marginBottom: 10,
  },

  // Footer
  footer: {
    position: "absolute",
    bottom: 20,
    left: 30,
    right: 30,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderTopWidth: 0.5,
    borderTopColor: BORDER_COLOR,
    paddingTop: 6,
  },
  footerText: {
    fontSize: 7,
    color: GRAY_TEXT,
  },
  footerPage: {
    fontSize: 7,
    color: GRAY_TEXT,
  },
});

// ---------------------------------------------------------------------------
// Column widths (percentage of table width, must sum to 100)
// ---------------------------------------------------------------------------

// # | Brand | Article | Name | unit | Qty | Price no VAT | Sum no VAT | VAT | Price w VAT | Total w VAT
const COL_WIDTHS = [
  "4%",  // #
  "9%",  // Brand
  "10%", // Article
  "18%", // Name
  "4%",  // unit
  "6%",  // Qty
  "10%", // Price no VAT
  "11%", // Sum no VAT
  "7%",  // VAT
  "10%", // Price w VAT
  "11%", // Total w VAT
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtMoney(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return "—";
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function fmtQty(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

interface ItemCalc {
  priceNoVat: number;
  sumNoVat: number;
  vatAmount: number;
  priceWithVat: number;
  totalWithVat: number;
}

function calcItem(item: QuoteItemRow, vatRate: number): ItemCalc {
  const basePrice = item.base_price_vat ?? 0;
  const qty = item.quantity ?? 0;

  const priceNoVat = vatRate > 0 ? basePrice / (1 + vatRate / 100) : basePrice;
  const sumNoVat = priceNoVat * qty;
  const totalWithVat = basePrice * qty;
  const vatAmount = totalWithVat - sumNoVat;

  return {
    priceNoVat,
    sumNoVat,
    vatAmount,
    priceWithVat: basePrice,
    totalWithVat,
  };
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface KPDocumentProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  logoBase64: string;
  vatRate?: number;
}

// ---------------------------------------------------------------------------
// Document
// ---------------------------------------------------------------------------

export function KPDocument({ quote, items, logoBase64, vatRate = 22 }: KPDocumentProps) {
  const currency = quote.currency ?? "RUB";

  // Calculate totals using VAT rate from calc engine (DDP+domestic=20%, export=0%)
  const calculations = items.map((item) => calcItem(item, vatRate));
  const totalNoVat = calculations.reduce((sum, c) => sum + c.sumNoVat, 0);
  const totalVat = calculations.reduce((sum, c) => sum + c.vatAmount, 0);
  const totalWithVat = calculations.reduce((sum, c) => sum + c.totalWithVat, 0);

  const customer = quote.customer;
  const contact = quote.contact_person;
  const manager = quote.created_by_profile;

  // Delivery info
  const deliveryAddress = [quote.delivery_city, quote.delivery_country]
    .filter(Boolean)
    .join(", ") || quote.delivery_address || "—";
  const incoterms = quote.incoterms ?? "—";
  const paymentTerms = quote.payment_terms ?? "—";
  const deliveryDays = quote.delivery_days != null ? `${quote.delivery_days} календарных дней` : "—";

  // Validity
  const validUntil = quote.valid_until ? fmtDate(quote.valid_until) : null;

  return (
    <Document>
      <Page size="A4" style={s.page}>
        {/* ---- Header band ---- */}
        <View style={s.headerBand}>
          <Image src={logoBase64} style={s.logo} />
          <Text style={s.headerTitle}>КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ</Text>
        </View>

        <View style={s.body}>
          {/* ---- Quote number ---- */}
          <Text style={s.quoteNumber}>
            КП {quote.idn_quote} от {fmtDate(quote.quote_date ?? quote.created_at)}
          </Text>

          {/* ---- Two-column info ---- */}
          <View style={s.infoRow}>
            {/* Left: Customer */}
            <View style={s.infoCol}>
              <Text style={s.infoTitle}>Заказчик</Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Компания: </Text>
                {customer?.name ?? "—"}
                {customer?.inn ? ` (ИНН ${customer.inn})` : ""}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Контакт: </Text>
                {contact?.name ?? "—"}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Тел: </Text>
                {contact?.phone ?? "—"}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Почта: </Text>
                {contact?.email ?? "—"}
              </Text>
            </View>

            {/* Right: Delivery terms */}
            <View style={s.infoCol}>
              <Text style={s.infoTitle}>Условия поставки</Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Адрес: </Text>
                {deliveryAddress}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Базис: </Text>
                {incoterms}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Оплата: </Text>
                {paymentTerms}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Дата КП: </Text>
                {fmtDate(quote.quote_date ?? quote.created_at)}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Срок: </Text>
                {deliveryDays}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Включено: </Text>
                НДС, страховка, таможенная очистка и доставка
              </Text>
            </View>
          </View>

          {/* ---- Supplier block ---- */}
          <View style={s.supplierBlock}>
            <Text style={s.infoTitle}>Поставщик</Text>
            <Text style={s.infoLine}>
              <Text style={s.infoLabel}>Компания: </Text>
              {`ООО "Мастер Бэринг" (ИНН 0242013464)`}
            </Text>
            <Text style={s.infoLine}>
              <Text style={s.infoLabel}>Менеджер: </Text>
              {manager?.full_name ?? "—"}
            </Text>
            <Text style={s.infoLine}>
              <Text style={s.infoLabel}>Почта: </Text>
              {quote.manager_email ?? "—"}
            </Text>
          </View>

          {/* ---- Summary cards ---- */}
          <View style={s.summaryRow}>
            <View style={s.summaryCard}>
              <Text style={s.summaryLabel}>Сумма без НДС</Text>
              <Text style={s.summaryValue}>
                {fmtMoney(totalNoVat)} {currency}
              </Text>
            </View>
            <View style={s.summaryCardAccent}>
              <Text style={s.summaryLabelAccent}>Сумма КП с НДС</Text>
              <Text style={s.summaryValueAccent}>
                {fmtMoney(totalWithVat)} {currency}
              </Text>
            </View>
            <View style={s.summaryCard}>
              <Text style={s.summaryLabel}>в т.ч. НДС</Text>
              <Text style={s.summaryValue}>
                {fmtMoney(totalVat)} {currency}
              </Text>
            </View>
          </View>

          {/* ---- Items table ---- */}
          <View style={s.table}>
            {/* Table header */}
            <View style={s.tableHeader}>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[0] }]}>#</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[1] }]}>Бренд</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[2] }]}>Артикул</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[3], textAlign: "left" }]}>Наименование</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[4] }]}>ед.</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[5] }]}>Кол-во</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[6] }]}>Цена б/НДС</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[7] }]}>Сумма б/НДС</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[8] }]}>НДС</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[9] }]}>Цена с НДС</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[10] }]}>Итого с НДС</Text>
            </View>

            {/* Data rows */}
            {items.map((item, idx) => {
              const calc = calculations[idx];
              const rowStyle = idx % 2 === 0 ? s.tableRow : s.tableRowAlt;
              return (
                <View key={item.id} style={rowStyle} wrap={false}>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[0] }]}>{idx + 1}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[1] }]}>{item.brand ?? "—"}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[2] }]}>{item.product_code ?? "—"}</Text>
                  <Text style={[s.tableCellLeft, { width: COL_WIDTHS[3] }]}>{item.product_name}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[4] }]}>{item.unit ?? "шт"}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[5] }]}>{fmtQty(item.quantity)}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[6] }]}>{fmtMoney(calc.priceNoVat)}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[7] }]}>{fmtMoney(calc.sumNoVat)}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[8] }]}>{fmtMoney(calc.vatAmount)}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[9] }]}>{fmtMoney(calc.priceWithVat)}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[10] }]}>{fmtMoney(calc.totalWithVat)}</Text>
                </View>
              );
            })}

            {/* ITOGO row */}
            <View style={s.tableTotalRow} wrap={false}>
              <Text style={[s.tableTotalCellLeft, { width: COL_WIDTHS[0] }]} />
              <Text style={[s.tableTotalCellLeft, { width: COL_WIDTHS[1] }]} />
              <Text style={[s.tableTotalCellLeft, { width: COL_WIDTHS[2] }]} />
              <Text style={[s.tableTotalCellLeft, { width: COL_WIDTHS[3] }]}>ИТОГО</Text>
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[4] }]} />
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[5] }]}>
                {fmtQty(items.reduce((sum, i) => sum + (i.quantity ?? 0), 0))}
              </Text>
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[6] }]} />
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[7] }]}>{fmtMoney(totalNoVat)}</Text>
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[8] }]}>{fmtMoney(totalVat)}</Text>
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[9] }]} />
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[10] }]}>{fmtMoney(totalWithVat)}</Text>
            </View>
          </View>

          {/* ---- Validity ---- */}
          {validUntil && (
            <Text style={s.validity}>
              Предложение действительно до {validUntil}
            </Text>
          )}
        </View>

        {/* ---- Footer ---- */}
        <View style={s.footer} fixed>
          <Text style={s.footerText}>
            {`ООО \u00ABМастер Бэринг\u00BB | ИНН 0242013464 | masterbearing.ru`}
          </Text>
          <Text
            style={s.footerPage}
            render={({ pageNumber, totalPages }) =>
              `${pageNumber} / ${totalPages}`
            }
          />
        </View>
      </Page>
    </Document>
  );
}
