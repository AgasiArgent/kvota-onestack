import { createClient } from "@/shared/lib/supabase/server";
import type {
  SettingsPageData,
  CalcSettings,
  StageDeadline,
} from "./types";

export async function fetchSettingsPageData(
  orgId: string
): Promise<SettingsPageData> {
  const supabase = await createClient();

  const [orgResult, calcResult, deadlinesResult] =
    await Promise.all([
      supabase
        .from("organizations")
        .select("id, name")
        .eq("id", orgId)
        .single(),
      supabase
        .from("calculation_settings")
        .select("id, organization_id, rate_forex_risk, rate_fin_comm, rate_loan_interest_daily")
        .eq("organization_id", orgId)
        .maybeSingle(),
      supabase
        .from("stage_deadlines" as never)
        .select("id, organization_id, stage, deadline_hours")
        .eq("organization_id", orgId)
        .order("stage"),
    ]);

  if (orgResult.error || !orgResult.data) {
    throw new Error(`Failed to load organization: ${orgResult.error?.message ?? 'not found'}`);
  }
  const organization = orgResult.data;

  return {
    organization,
    calcSettings: (calcResult.data as CalcSettings) ?? null,
    stageDeadlines: ((deadlinesResult as { data: StageDeadline[] | null }).data ?? []) as StageDeadline[],
  };
}
