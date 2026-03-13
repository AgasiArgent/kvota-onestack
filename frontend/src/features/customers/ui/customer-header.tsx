import Link from "next/link";
import { ArrowLeft, Plus, Building2 } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Customer } from "@/entities/customer";

interface Props {
  customer: Customer;
}

export function CustomerHeader({ customer }: Props) {
  return (
    <div className="mb-6">
      <Link
        href="/customers"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-3"
      >
        <ArrowLeft size={16} />
        Клиенты
      </Link>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 size={24} className="text-slate-400" />
          <h1 className="text-2xl font-bold">{customer.name}</h1>
          <Badge variant={customer.is_active ? "default" : "secondary"}>
            {customer.is_active ? "Активен" : "Неактивен"}
          </Badge>
        </div>
        <Link href={`/quotes/new?customer_id=${customer.id}`} className={buttonVariants()}>
          <Plus size={16} />
          Создать КП
        </Link>
      </div>
    </div>
  );
}
