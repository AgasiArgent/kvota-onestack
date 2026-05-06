import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchDeclarations,
  fetchDeclarationItems,
} from "@/entities/customs-declaration";
import { DeclarationsTable } from "@/features/customs-declarations";
import type { CustomsDeclarationItem } from "@/entities/customs-declaration";

// Mirror sidebar-menu.ts — sidebar advertises this link to head_of_customs
// + head_of_logistics + finance (dual-hat per PR #105) and top_manager
// (head-tier access per PR #126). Without these slugs the page silently
// redirects to / for users the nav promised access to.
const ALLOWED_ROLES = [
  "customs",
  "head_of_customs",
  "head_of_logistics",
  "admin",
  "top_manager",
  "finance",
];

export default async function CustomsDeclarationsPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const hasAccess = user.roles.some((r) => ALLOWED_ROLES.includes(r));
  if (!hasAccess) redirect("/");

  const declarations = await fetchDeclarations(user.orgId);

  // Batch-fetch items for all declarations in parallel
  const itemEntries = await Promise.all(
    declarations.map(async (d) => {
      const items = await fetchDeclarationItems(d.id, user.orgId!);
      return [d.id, items] as [string, CustomsDeclarationItem[]];
    })
  );
  const allItems: Record<string, CustomsDeclarationItem[]> =
    Object.fromEntries(itemEntries);

  return (
    <div>
      <DeclarationsTable declarations={declarations} allItems={allItems} />
    </div>
  );
}
