"use client";

import { createClient } from "@/shared/lib/supabase/client";

export interface OksmCountry {
  oksm_digital: number;
  iso_alpha2: string;
  name_ru: string;
  is_unfriendly: boolean;
}

/**
 * Fetch the full ОКСМ countries reference list directly from
 * `kvota.countries` via the browser Supabase client.
 *
 * Reference data is small (~250 rows) and stable — direct read is OK
 * per the spec design § "Supabase JS direct read (countries lookup)".
 *
 * Business logic (resolve-rates, freeze) goes through the Python API only.
 */
export async function fetchOksmCountries(): Promise<OksmCountry[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("countries")
    .select("oksm_digital, iso_alpha2, name_ru, is_unfriendly")
    .order("name_ru");

  if (error) {
    throw new Error(`Не удалось загрузить список стран: ${error.message}`);
  }
  return data ?? [];
}
