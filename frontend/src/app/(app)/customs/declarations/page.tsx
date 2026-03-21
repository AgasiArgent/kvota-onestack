import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchDeclarations,
  fetchDeclarationItems,
} from "@/entities/customs-declaration";
import { DeclarationsTable } from "@/features/customs-declarations";
import type { CustomsDeclarationItem } from "@/entities/customs-declaration";

const ALLOWED_ROLES = ["customs", "admin", "finance"];

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
