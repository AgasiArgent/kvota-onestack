"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";

import { createClient } from "@/shared/lib/supabase/server";

/**
 * Multi-segment client payment terms (Testing 2 row 46, spec
 * `.kiro/specs/payment-segments-row-46/`). 9 fields, 1:1 with calc engine
 * PaymentTerms (anchor 1 reuses existing `advance_percent_from_client` +
 * `payment_deferral_days`; anchor 5 % is derived as `100 - Σ(anchors 1-4)`).
 *
 * Sum check (anchors 1-4 ≤ 100) is enforced in three layers:
 *   - DB CHECK constraint `spec_payment_pct_sum_max` (migration 324)
 *   - Server-action zod refine (defence in depth)
 *   - Client-side live validation in `<PaymentSegmentsBlock>` (UX hint)
 */
const PaymentSegmentsSchema = z
  .object({
    advance_percent_from_client: z.number().min(0).max(100),
    payment_deferral_days: z.number().int().min(0),
    payment_on_loading_pct: z.number().min(0).max(100),
    payment_on_loading_days: z.number().int().min(0),
    payment_on_country_arrival_pct: z.number().min(0).max(100),
    payment_on_country_arrival_days: z.number().int().min(0),
    payment_on_customs_clearance_pct: z.number().min(0).max(100),
    payment_on_customs_clearance_days: z.number().int().min(0),
    payment_on_receiving_days: z.number().int().min(0),
  })
  .refine(
    (data) =>
      data.advance_percent_from_client +
        data.payment_on_loading_pct +
        data.payment_on_country_arrival_pct +
        data.payment_on_customs_clearance_pct <=
      100,
    {
      message:
        "Сумма % по анкорам 1-4 (аванс/погрузка/прибытие/таможня) не должна превышать 100",
    }
  );

export type PaymentSegmentsInput = z.infer<typeof PaymentSegmentsSchema>;

export async function updateSpecificationPayment(
  specId: string,
  segments: PaymentSegmentsInput
): Promise<{ success: true }> {
  const parsed = PaymentSegmentsSchema.parse(segments);
  const supabase = await createClient();

  const { error } = await supabase
    .from("specifications")
    .update({
      advance_percent_from_client: parsed.advance_percent_from_client,
      payment_deferral_days: parsed.payment_deferral_days,
      payment_on_loading_pct: parsed.payment_on_loading_pct,
      payment_on_loading_days: parsed.payment_on_loading_days,
      payment_on_country_arrival_pct: parsed.payment_on_country_arrival_pct,
      payment_on_country_arrival_days: parsed.payment_on_country_arrival_days,
      payment_on_customs_clearance_pct: parsed.payment_on_customs_clearance_pct,
      payment_on_customs_clearance_days: parsed.payment_on_customs_clearance_days,
      payment_on_receiving_days: parsed.payment_on_receiving_days,
      updated_at: new Date().toISOString(),
    })
    .eq("id", specId);

  if (error) {
    // Log the original DB error before bubbling user-facing message
    console.error("updateSpecificationPayment failed", { specId, error });
    throw new Error(error.message);
  }

  // Revalidate the quote detail (specification lives on quote tabs) so
  // server-side reads reflect the new payment terms on next navigation.
  revalidatePath("/quotes", "layout");
  return { success: true };
}
