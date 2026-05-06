import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { LocationsPage } from "@/features/locations";
import {
  fetchLocations,
  fetchLocationStats,
  fetchLocationCountries,
} from "@/features/locations/api/server-queries";

interface Props {
  searchParams: Promise<{
    q?: string;
    country?: string;
    status?: string;
    type?: string;
  }>;
}

// Mirror sidebar-menu.ts — sidebar advertises this link to head_of_logistics
// + head_of_customs (dual-hat per PR #105) and top_manager (head-tier
// access per PR #126). Without these slugs the page silently redirects
// to / for users the nav promised access to.
const ALLOWED_ROLES = [
  "admin",
  "logistics",
  "head_of_logistics",
  "customs",
  "head_of_customs",
  "procurement",
  "procurement_senior",
  "top_manager",
];

export default async function LocationsRoute({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed = user.roles.some((r) => ALLOWED_ROLES.includes(r));
  if (!isAllowed) redirect("/");

  const params = await searchParams;
  const search = params.q ?? "";
  const country = params.country ?? "";
  const status = params.status ?? "";
  const type = params.type ?? "";

  const [locations, stats, countries] = await Promise.all([
    fetchLocations(user.orgId, { search, country, status, type }),
    fetchLocationStats(user.orgId),
    fetchLocationCountries(user.orgId),
  ]);

  const canEditType = user.roles.some(
    (r) =>
      r === "admin" || r === "head_of_logistics" || r === "head_of_customs",
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Локации</h1>
      <LocationsPage
        locations={locations}
        stats={stats}
        countries={countries}
        initialSearch={search}
        initialCountry={country}
        initialStatus={status}
        initialType={type}
        canEditType={canEditType}
      />
    </div>
  );
}
