import { createClient } from "@/shared/lib/supabase/server";

export async function fetchDocumentCount(quoteId: string): Promise<number> {
  const supabase = await createClient();
  const { count, error } = await supabase
    .from("documents")
    .select("id", { count: "exact", head: true })
    .eq("parent_quote_id", quoteId);

  if (error) return 0;
  return count ?? 0;
}
