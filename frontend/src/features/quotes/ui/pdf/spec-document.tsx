import {
  Document,
  Page,
  View,
  Text,
  Image,
  StyleSheet,
  Font,
} from "@react-pdf/renderer";

// ---------------------------------------------------------------------------
// Font registration (same as KP document)
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

// Break long words (article codes, SKUs) that have no natural break points
Font.registerHyphenationCallback((word) =>
  word.length > 12 ? Array.from(word) : [word]
);

// ---------------------------------------------------------------------------
// Brand colors
// ---------------------------------------------------------------------------

const NAVY = "#005BAA";
const DARK_TEXT = "#161616";
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
  headerBand: {
    backgroundColor: NAVY,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 30,
    paddingVertical: 14,
  },
  logo: { height: 44, width: 140, objectFit: "contain" },
  headerTitle: { color: WHITE, fontSize: 16, fontWeight: 700, letterSpacing: 1 },
  body: { paddingHorizontal: 30 },
  specNumber: { fontSize: 11, fontWeight: 700, marginTop: 14, marginBottom: 10 },

  // Info blocks
  infoRow: { flexDirection: "row", gap: 16, marginBottom: 12 },
  infoCol: { flex: 1, padding: 10, borderWidth: 1, borderColor: BORDER_COLOR, borderRadius: 3 },
  infoTitle: { fontSize: 8, fontWeight: 700, color: NAVY, marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 },
  infoLine: { fontSize: 8.5, marginBottom: 2.5, color: DARK_TEXT },
  infoLabel: { color: GRAY_TEXT },

  // Table
  table: { marginBottom: 10 },
  tableHeader: { flexDirection: "row", backgroundColor: NAVY, paddingVertical: 5, paddingHorizontal: 2 },
  tableHeaderCell: { color: WHITE, fontSize: 7, fontWeight: 700, textAlign: "center", paddingHorizontal: 2 },
  tableRow: { flexDirection: "row", paddingVertical: 4, paddingHorizontal: 2, borderBottomWidth: 0.5, borderBottomColor: BORDER_COLOR },
  tableRowAlt: { flexDirection: "row", paddingVertical: 4, paddingHorizontal: 2, backgroundColor: TABLE_ALT, borderBottomWidth: 0.5, borderBottomColor: BORDER_COLOR },
  tableCell: { fontSize: 7.5, textAlign: "center", paddingHorizontal: 2 },
  tableCellLeft: { fontSize: 7.5, textAlign: "left", paddingHorizontal: 2 },
  tableTotalRow: { flexDirection: "row", paddingVertical: 5, paddingHorizontal: 2, borderTopWidth: 1.5, borderTopColor: NAVY },
  tableTotalCell: { fontSize: 8.5, fontWeight: 700, textAlign: "center", paddingHorizontal: 2 },
  tableTotalCellLeft: { fontSize: 8.5, fontWeight: 700, textAlign: "left", paddingHorizontal: 2 },

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
  footerText: { fontSize: 7, color: GRAY_TEXT },
  footerPage: { fontSize: 7, color: GRAY_TEXT },
});

// Column widths: # | Brand | Article | Name | Unit | Qty | Price | Total
const COL_WIDTHS = ["5%", "12%", "13%", "26%", "6%", "8%", "15%", "15%"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtMoney(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return "—";
  return new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

function fmtQty(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value);
}

function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface SpecDocumentProps {
  specNumber: string;
  signDate: string | null;
  readinessPeriod: string | null;
  contractNumber: string | null;
  contractDate: string | null;
  customerName: string;
  customerInn: string | null;
  quoteCurrency: string;
  quoteIdn: string;
  items: {
    brand: string | null;
    product_code: string | null;
    product_name: string;
    unit: string | null;
    quantity: number | null;
    base_price_vat: number | null;
  }[];
  logoBase64: string;
}

// ---------------------------------------------------------------------------
// Document
// ---------------------------------------------------------------------------

export function SpecDocument({
  specNumber,
  signDate,
  readinessPeriod,
  contractNumber,
  contractDate,
  customerName,
  customerInn,
  quoteCurrency,
  quoteIdn,
  items,
  logoBase64,
}: SpecDocumentProps) {
  const currency = quoteCurrency || "RUB";

  const totals = items.reduce(
    (acc, item) => {
      const qty = item.quantity ?? 0;
      const price = item.base_price_vat ?? 0;
      return { totalQty: acc.totalQty + qty, totalSum: acc.totalSum + price * qty };
    },
    { totalQty: 0, totalSum: 0 }
  );

  return (
    <Document>
      <Page size="A4" style={s.page}>
        {/* Header band */}
        <View style={s.headerBand}>
          <Image src={logoBase64} style={s.logo} />
          <Text style={s.headerTitle}>СПЕЦИФИКАЦИЯ</Text>
        </View>

        <View style={s.body}>
          {/* Spec number */}
          <Text style={s.specNumber}>
            {specNumber} к КП {quoteIdn}
          </Text>

          {/* Info columns */}
          <View style={s.infoRow}>
            <View style={s.infoCol}>
              <Text style={s.infoTitle}>Заказчик</Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Компания: </Text>
                {customerName}{customerInn ? ` (ИНН ${customerInn})` : ""}
              </Text>
            </View>
            <View style={s.infoCol}>
              <Text style={s.infoTitle}>Условия</Text>
              {contractNumber && (
                <Text style={s.infoLine}>
                  <Text style={s.infoLabel}>Договор: </Text>
                  {contractNumber}{contractDate ? ` от ${fmtDate(contractDate)}` : ""}
                </Text>
              )}
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Дата подписания: </Text>
                {fmtDate(signDate)}
              </Text>
              <Text style={s.infoLine}>
                <Text style={s.infoLabel}>Срок поставки: </Text>
                {readinessPeriod ?? "—"}
              </Text>
            </View>
          </View>

          {/* Items table */}
          <View style={s.table}>
            <View style={s.tableHeader}>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[0] }]}>#</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[1] }]}>Бренд</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[2] }]}>Артикул</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[3], textAlign: "left" }]}>Наименование</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[4] }]}>ед.</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[5] }]}>Кол-во</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[6] }]}>Цена</Text>
              <Text style={[s.tableHeaderCell, { width: COL_WIDTHS[7] }]}>Сумма</Text>
            </View>

            {items.map((item, idx) => {
              const qty = item.quantity ?? 0;
              const price = item.base_price_vat ?? 0;
              const rowStyle = idx % 2 === 0 ? s.tableRow : s.tableRowAlt;
              return (
                <View key={idx} style={rowStyle} wrap={false}>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[0] }]}>{idx + 1}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[1] }]}>{item.brand ?? "—"}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[2] }]}>{item.product_code ?? "—"}</Text>
                  <Text style={[s.tableCellLeft, { width: COL_WIDTHS[3] }]}>{item.product_name}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[4] }]}>{item.unit ?? "шт"}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[5] }]}>{fmtQty(qty)}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[6] }]}>{fmtMoney(price)}</Text>
                  <Text style={[s.tableCell, { width: COL_WIDTHS[7] }]}>{fmtMoney(price * qty)}</Text>
                </View>
              );
            })}

            <View style={s.tableTotalRow} wrap={false}>
              <Text style={[s.tableTotalCellLeft, { width: COL_WIDTHS[0] }]} />
              <Text style={[s.tableTotalCellLeft, { width: COL_WIDTHS[1] }]} />
              <Text style={[s.tableTotalCellLeft, { width: COL_WIDTHS[2] }]} />
              <Text style={[s.tableTotalCellLeft, { width: COL_WIDTHS[3] }]}>ИТОГО</Text>
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[4] }]} />
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[5] }]}>{fmtQty(totals.totalQty)}</Text>
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[6] }]} />
              <Text style={[s.tableTotalCell, { width: COL_WIDTHS[7] }]}>
                {fmtMoney(totals.totalSum)} {currency}
              </Text>
            </View>
          </View>
        </View>

        {/* Footer */}
        <View style={s.footer} fixed>
          <Text style={s.footerText}>
            {`ООО \u00ABМастер Бэринг\u00BB | ИНН 0242013464 | masterbearing.ru`}
          </Text>
          <Text
            style={s.footerPage}
            render={({ pageNumber, totalPages }) => `${pageNumber} / ${totalPages}`}
          />
        </View>
      </Page>
    </Document>
  );
}
