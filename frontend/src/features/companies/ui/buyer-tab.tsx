"use client";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { BuyerCompany } from "../model/types";

interface Props {
  companies: BuyerCompany[];
}

export function BuyerTab({ companies }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[30%]">Название</TableHead>
          <TableHead>Код</TableHead>
          <TableHead>ИНН</TableHead>
          <TableHead>КПП</TableHead>
          <TableHead>Страна</TableHead>
          <TableHead>Статус</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {companies.map((company) => (
          <TableRow key={company.id}>
            <TableCell className="font-medium">{company.name}</TableCell>
            <TableCell className="text-text-muted tabular-nums">
              {company.company_code || "\u2014"}
            </TableCell>
            <TableCell className="text-text-muted tabular-nums">
              {company.inn || "\u2014"}
            </TableCell>
            <TableCell className="text-text-muted tabular-nums">
              {company.kpp || "\u2014"}
            </TableCell>
            <TableCell className="text-text-muted">
              {company.country || "\u2014"}
            </TableCell>
            <TableCell>
              <Badge variant={company.is_active ? "default" : "secondary"}>
                {company.is_active ? "Активна" : "Неактивна"}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
        {companies.length === 0 && (
          <TableRow>
            <TableCell
              colSpan={6}
              className="text-center py-8 text-text-subtle"
            >
              Юрлица-закупки не найдены
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
