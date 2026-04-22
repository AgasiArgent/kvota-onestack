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

const ALLOWED_ROLES = ["admin", "logistics", "customs", "procurement", "procurement_senior"];

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
      />
    </div>
  );
}
