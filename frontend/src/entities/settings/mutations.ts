import { createClient } from "@/shared/lib/supabase/client";
import type { StageDeadline } from "./types";

export async function upsertCalcSettings(
  orgId: string,
  data: {
    rate_forex_risk: number;
    rate_fin_comm: number;
    rate_loan_interest_daily: number;
  }
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("calculation_settings")
    .upsert(
      {
        organization_id: orgId,
        ...data,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "organization_id" }
    );

  if (error) throw error;
}

export async function upsertStageDeadlines(
  orgId: string,
  deadlines: Array<{ stage: string; deadline_hours: number }>
): Promise<StageDeadline[]> {
  const supabase = createClient();

  const rows = deadlines.map((d) => ({
    organization_id: orgId,
    stage: d.stage,
    deadline_hours: d.deadline_hours,
    updated_at: new Date().toISOString(),
  }));

  const { data, error } = await supabase
    .from("stage_deadlines" as never)
    .upsert(rows as never, { onConflict: "organization_id,stage" })
    .select("id, organization_id, stage, deadline_hours");

  if (error) throw error;

  return (data ?? []) as StageDeadline[];
}
