"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Plus, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CreateQuoteDialog } from "@/features/quotes";
import type { Customer } from "@/entities/customer";

interface Props {
  customer: Customer;
  orgId: string;
  userId: string;
}

export function CustomerHeader({ customer, orgId, userId }: Props) {
  const [createQuoteOpen, setCreateQuoteOpen] = useState(false);

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
        <Button
          onClick={() => setCreateQuoteOpen(true)}
          className="bg-accent text-white hover:bg-accent-hover"
        >
          <Plus size={16} />
          Создать КП
        </Button>
      </div>
      <CreateQuoteDialog
        orgId={orgId}
        userId={userId}
        open={createQuoteOpen}
        onOpenChange={setCreateQuoteOpen}
        preselectedCustomer={{ id: customer.id, name: customer.name }}
      />
    </div>
  );
}
