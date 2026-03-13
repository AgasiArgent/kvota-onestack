"use client";

import Link from "next/link";
import { ArrowLeft, Plus, Building2 } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { config } from "@/shared/config";
import type { Customer } from "@/entities/customer";

interface Props {
  customer: Customer;
}

export function CustomerHeader({ customer }: Props) {
  return (
    <div className="mb-6">
      <Link
        href="/customers"
        className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text mb-3"
      >
        <ArrowLeft size={16} />
        Клиенты
      </Link>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 size={24} className="text-text-subtle" />
          <h1 className="text-2xl font-bold">{customer.name}</h1>
          <Badge variant={customer.status === "active" ? "default" : "secondary"}>
            {customer.status === "active" ? "Активен" : "Неактивен"}
          </Badge>
        </div>
        <a
          href={`${config.legacyAppUrl}/quotes/new?customer_id=${customer.id}`}
          target="_blank"
          rel="noopener"
          className={buttonVariants()}
        >
          <Plus size={16} />
          Создать КП
        </a>
      </div>
    </div>
  );
}
