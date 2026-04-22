/**
 * Shared workflow-status vocabulary for the Quote entity.
 *
 * Previously each feature owned its own copy of this map, which is how we
 * ended up with a raw enum (`pending_logistics_and_customs`) leaking through
 * as a Badge label on the cost-analysis page after the Next.js port.
 *
 * Keep new workflow statuses added here — features (quote-sticky-header,
 * cost-analysis, customs-info-block, participants-block, etc.) should import
 * these maps instead of redefining them locally.
 */

/** Russian label for each workflow status. Fallback to the raw value if unknown. */
export const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  pending_procurement: "На закупке",
  procurement_complete: "Закупка завершена",
  pending_logistics: "На логистике",
  pending_customs: "На таможне",
  pending_logistics_and_customs: "Логистика и таможня",
  calculated: "Рассчитано",
  pending_approval: "На согласовании",
  pending_quote_control: "Контроль КП",
  pending_spec_control: "Контроль спецификации",
  pending_sales_review: "Ревью продаж",
  approved: "Одобрено",
  sent_to_client: "Отправлено клиенту",
  accepted: "Принято",
  spec_signed: "Сделка",
  rejected: "Отклонено",
  cancelled: "Отменено",
};

/** Tailwind class string for each status badge — paired with STATUS_LABELS. */
export const STATUS_BADGE_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  pending_procurement: "bg-amber-100 text-amber-700",
  procurement_complete: "bg-amber-100 text-amber-700",
  pending_logistics: "bg-indigo-100 text-indigo-700",
  pending_customs: "bg-indigo-100 text-indigo-700",
  pending_logistics_and_customs: "bg-indigo-100 text-indigo-700",
  calculated: "bg-blue-100 text-blue-700",
  pending_approval: "bg-blue-100 text-blue-700",
  pending_quote_control: "bg-blue-100 text-blue-700",
  pending_spec_control: "bg-blue-100 text-blue-700",
  pending_sales_review: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  sent_to_client: "bg-green-100 text-green-700",
  accepted: "bg-green-200 text-green-800 font-semibold",
  spec_signed: "bg-green-200 text-green-800 font-semibold",
  rejected: "bg-red-100 text-red-700",
  cancelled: "bg-red-100 text-red-700",
};

/** Convenience accessor with fallback. */
export function getStatusLabel(status: string | null | undefined): string {
  if (!status) return STATUS_LABELS.draft;
  return STATUS_LABELS[status] ?? status;
}
