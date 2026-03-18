import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchSettingsPageData } from "@/entities/settings/queries";
import { PhmbSettingsTabs } from "@/features/settings/ui/phmb-settings-tabs";

interface Props {
  searchParams: Promise<{ tab?: string }>;
}

export default async function PhmbSettingsPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const isAdminOrSales =
    user.roles.includes("admin") || user.roles.includes("sales");
  if (!isAdminOrSales) redirect("/phmb");
  if (!user.orgId) redirect("/phmb");

  const data = await fetchSettingsPageData(user.orgId);
  const { tab } = await searchParams;

  return (
    <PhmbSettingsTabs data={data} defaultTab={tab ?? "markup"} />
  );
}
