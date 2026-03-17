"use client";

import Link from "next/link";
import { ArrowLeft, Building2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { SupplierDetail } from "@/entities/supplier/types";

interface Props {
  supplier: SupplierDetail;
}

export function SupplierHeader({ supplier }: Props) {
  return (
    <div className="mb-6">
      <Link
        href="/suppliers"
        className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text mb-3"
      >
        <ArrowLeft size={16} />
        Поставщики
      </Link>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 size={24} className="text-text-subtle" />
          <h1 className="text-2xl font-bold">{supplier.name}</h1>
          {supplier.supplier_code && (
            <Badge variant="secondary">{supplier.supplier_code}</Badge>
          )}
          <Badge variant={supplier.is_active ? "default" : "secondary"}>
            {supplier.is_active ? "Активен" : "Неактивен"}
          </Badge>
        </div>
      </div>
    </div>
  );
}
