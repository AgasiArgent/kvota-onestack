import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user/server";
import { fetchSettingsPageData } from "@/entities/settings/queries";
import { SettingsTabs } from "@/features/settings";

interface Props {
  searchParams: Promise<{ tab?: string }>;
}

export default async function SettingsPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const isAdmin = user.roles.includes("admin");
  if (!isAdmin) redirect("/dashboard");

  if (!user.orgId) redirect("/dashboard");

  const data = await fetchSettingsPageData(user.orgId);

  const { tab } = await searchParams;

  return <SettingsTabs data={data} defaultTab={tab ?? "calc"} />;
}
