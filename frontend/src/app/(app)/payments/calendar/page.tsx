import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user/server";
import { createAdminClient } from "@/shared/lib/supabase/server";
import { PaymentsCalendar } from "@/features/payments-calendar";

export default async function PaymentsCalendarPage() {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const hasAccess = user.roles.some((r) =>
    ["finance", "admin", "top_manager"].includes(r)
  );
  if (!hasAccess) redirect("/");

  const admin = createAdminClient();

  const { data: rawPayments } = await admin
    .from("payment_schedule")
    .select(
      "id, specification_id, payment_number, days_term, calculation_variant, expected_payment_date, actual_payment_date, payment_amount, payment_currency, payment_purpose, comment"
    )
    .order("expected_payment_date", { ascending: true });

  const paymentRows = rawPayments ?? [];

  // Fetch specification numbers for all unique specification_ids
  const specIds = [...new Set(paymentRows.map((p) => p.specification_id))];
  const specMap = new Map<string, string | null>();

  if (specIds.length > 0) {
    const { data: specs } = await admin
      .from("specifications")
      .select("id, specification_number")
      .in("id", specIds)
      .is("deleted_at", null);

    for (const s of specs ?? []) {
      specMap.set(s.id, s.specification_number);
    }
  }

  const payments = paymentRows.map((p) => ({
    id: p.id,
    specification_id: p.specification_id,
    payment_number: p.payment_number,
    days_term: p.days_term,
    calculation_variant: p.calculation_variant,
    expected_payment_date: p.expected_payment_date,
    actual_payment_date: p.actual_payment_date,
    payment_amount: p.payment_amount,
    payment_currency: p.payment_currency,
    payment_purpose: p.payment_purpose,
    comment: p.comment,
    specification_number: specMap.get(p.specification_id) ?? null,
  }));

  return <PaymentsCalendar payments={payments} />;
}
