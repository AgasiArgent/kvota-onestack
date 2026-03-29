export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  invoice_scan: "Скан инвойса",
  proforma_scan: "Проформа",
  payment_order: "Платёжка",
  contract: "Договор",
  certificate: "Сертификат",
  ttn: "ТТН",
  cmr: "CMR",
  bill_of_lading: "Коносамент",
  customs_declaration: "ТД",
  specification_signed_scan: "Скан спецификации",
  upd: "УПД",
  other: "Другое",
};

export const ENTITY_TYPE_LABELS: Record<string, string> = {
  quote: "Документы КП",
  supplier_invoice: "Инвойсы поставщиков",
  quote_item: "Сертификаты позиций",
  specification: "Спецификация",
};

export const DOCUMENT_TYPE_OPTIONS = Object.entries(DOCUMENT_TYPE_LABELS).map(
  ([value, label]) => ({ value, label })
);

const MIME_ICON_MAP: Record<string, string> = {
  "application/pdf": "pdf",
  "image/jpeg": "image",
  "image/png": "image",
  "image/webp": "image",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "spreadsheet",
  "application/vnd.ms-excel": "spreadsheet",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "doc",
  "application/msword": "doc",
};

export function getMimeCategory(mimeType: string | null): string {
  if (!mimeType) return "file";
  return MIME_ICON_MAP[mimeType] ?? "file";
}

export function formatFileSize(bytes: number | null): string {
  if (bytes == null || bytes === 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
