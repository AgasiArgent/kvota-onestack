"use client";

import { useState } from "react";
import { Plus, Pencil } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { BuyerCompany } from "../model/types";
import { BuyerCompanyDialog } from "./buyer-company-dialog";

interface Props {
  companies: BuyerCompany[];
  orgId: string;
  /**
   * Whether the current user is authorized to open the Создать/Редактировать
   * dialog (Testing 2 row 82 follow-up). Computed server-side via
   * `canManageBuyerCompany(user.roles)` and aligned with the widened
   * buyer_companies INSERT/UPDATE RLS policy (migration 331). Defaults to
   * `false` for safety; callers that omit the prop see read-only mode.
   */
  canManage?: boolean;
}

export function BuyerTab({ companies, orgId, canManage = false }: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<BuyerCompany | null>(null);

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(company: BuyerCompany) {
    setEditing(company);
    setDialogOpen(true);
  }

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex justify-end">
          <Button
            size="sm"
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={openCreate}
          >
            <Plus size={16} />
            Создать юрлицо
          </Button>
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[30%]">Название</TableHead>
            <TableHead>Код</TableHead>
            <TableHead>ИНН</TableHead>
            <TableHead>КПП</TableHead>
            <TableHead>Страна</TableHead>
            <TableHead>Статус</TableHead>
            {canManage && <TableHead className="w-[80px]" />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {companies.map((company) => (
            <TableRow key={company.id}>
              <TableCell className="font-medium">{company.name}</TableCell>
              <TableCell className="text-text-muted tabular-nums">
                {company.company_code || "—"}
              </TableCell>
              <TableCell className="text-text-muted tabular-nums">
                {company.inn || "—"}
              </TableCell>
              <TableCell className="text-text-muted tabular-nums">
                {company.kpp || "—"}
              </TableCell>
              <TableCell className="text-text-muted">
                {company.country || "—"}
              </TableCell>
              <TableCell>
                <Badge variant={company.is_active ? "default" : "secondary"}>
                  {company.is_active ? "Активна" : "Неактивна"}
                </Badge>
              </TableCell>
              {canManage && (
                <TableCell>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEdit(company)}
                    aria-label={`Редактировать ${company.name}`}
                  >
                    <Pencil size={14} />
                    Изменить
                  </Button>
                </TableCell>
              )}
            </TableRow>
          ))}
          {companies.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={canManage ? 7 : 6}
                className="text-center py-8 text-text-subtle"
              >
                Юрлица-закупки не найдены
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {canManage && (
        <BuyerCompanyDialog
          orgId={orgId}
          initial={editing}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  );
}
