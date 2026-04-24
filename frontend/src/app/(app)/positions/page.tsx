import { redirect } from "next/navigation";
import { fetchPositionsList } from "@/entities/position/queries";
import { getSessionUser } from "@/entities/user/server";
import { PositionsTable } from "@/features/positions";

interface Props {
  searchParams: Promise<{
    search?: string;
    availability?: string;
    brand?: string;
    moz?: string;
    dateFrom?: string;
    dateTo?: string;
    page?: string;
  }>;
}

export default async function PositionsPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed =
    user.roles.includes("admin") || user.roles.includes("procurement") || user.roles.includes("procurement_senior");
  if (!isAllowed) redirect("/");

  const params = await searchParams;
  const search = params.search ?? "";
  const availability = params.availability as "available" | "unavailable" | undefined;
  const brand = params.brand ?? "";
  const mozId = params.moz ?? "";
  const dateFrom = params.dateFrom ?? "";
  const dateTo = params.dateTo ?? "";
  const page = parseInt(params.page ?? "1", 10);

  const { products, details, total, filterOptions } = await fetchPositionsList(
    user.orgId,
    {
      search: search || undefined,
      availability: availability === "available" || availability === "unavailable" ? availability : undefined,
      brand: brand && brand !== "all" ? brand : undefined,
      mozId: mozId && mozId !== "all" ? mozId : undefined,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
      page,
    }
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Реестр позиций</h1>
      <PositionsTable
        products={products}
        details={details}
        total={total}
        filterOptions={filterOptions}
        initialSearch={search}
        initialBrand={brand}
        initialMozId={mozId}
        initialAvailability={params.availability ?? ""}
        initialDateFrom={dateFrom}
        initialDateTo={dateTo}
        initialPage={page}
      />
    </div>
  );
}
