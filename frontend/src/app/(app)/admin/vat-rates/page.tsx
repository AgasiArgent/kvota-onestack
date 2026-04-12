import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { VatRatesTable } from "@/features/admin/ui/vat-rates-table";

export default async function VatRatesPage() {
  const user = await getSessionUser();

  if (!user) {
    redirect("/login");
  }

  if (!user.roles.includes("admin")) {
    redirect("/");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Ставки НДС по странам</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Управление ставками НДС для автоматического заполнения при создании КП
          поставщику
        </p>
      </div>
      <VatRatesTable />
    </div>
  );
}
