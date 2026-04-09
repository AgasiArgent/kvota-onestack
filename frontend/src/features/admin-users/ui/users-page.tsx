"use client";

import { useState, useMemo } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";
import { Search, Users, MessageCircle, Plus } from "lucide-react";
import type { OrgMember, RoleOption } from "@/entities/admin/types";
import { ROLE_COLORS } from "@/entities/admin/types";
import { ROLE_LABELS_RU } from "@/entities/user/types";
import { CreateUserDialog } from "./create-user-dialog";
import { UserEditSheet } from "./user-edit-sheet";

interface SalesGroupOption {
  id: string;
  name: string;
}

interface UsersPageProps {
  members: OrgMember[];
  allRoles: RoleOption[];
  salesGroups: SalesGroupOption[];
  orgId: string;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function UsersPageClient({
  members,
  allRoles,
  salesGroups,
  orgId,
}: UsersPageProps) {
  const [search, setSearch] = useState("");
  const [selectedMember, setSelectedMember] = useState<OrgMember | null>(null);
  const [isEditSheetOpen, setIsEditSheetOpen] = useState(false);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);

  const telegramCount = members.filter((m) => m.telegram_username).length;
  const activeCount = members.filter((m) => m.status === "active").length;

  const filtered = useMemo(() => {
    if (!search) return members;
    const q = search.toLowerCase();
    return members.filter(
      (m) =>
        (m.full_name?.toLowerCase().includes(q) ?? false) ||
        m.email.toLowerCase().includes(q)
    );
  }, [members, search]);

  function handleRowClick(member: OrgMember) {
    setSelectedMember(member);
    setIsEditSheetOpen(true);
  }

  function handleEditSheetClose() {
    setIsEditSheetOpen(false);
    setSelectedMember(null);
  }

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="flex items-center gap-3 p-4">
          <div className="flex size-10 items-center justify-center rounded-lg bg-blue-100">
            <Users size={20} className="text-blue-700" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Всего пользователей</p>
            <p className="text-2xl font-bold">{members.length}</p>
          </div>
        </Card>
        <Card className="flex items-center gap-3 p-4">
          <div className="flex size-10 items-center justify-center rounded-lg bg-green-100">
            <Users size={20} className="text-green-700" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Активных</p>
            <p className="text-2xl font-bold">{activeCount}</p>
          </div>
        </Card>
        <Card className="flex items-center gap-3 p-4">
          <div className="flex size-10 items-center justify-center rounded-lg bg-green-100">
            <MessageCircle size={20} className="text-green-700" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">С Telegram</p>
            <p className="text-2xl font-bold">{telegramCount}</p>
          </div>
        </Card>
      </div>

      {/* Search + Create button */}
      <div className="flex items-center gap-4">
        <div className="relative max-w-sm flex-1">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            placeholder="Поиск по имени или email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus size={16} />
          Добавить пользователя
        </Button>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ФИО</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Роли</TableHead>
            <TableHead>Статус</TableHead>
            <TableHead>Telegram</TableHead>
            <TableHead>Дата</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((member) => (
            <TableRow
              key={member.user_id}
              className="cursor-pointer"
              onClick={() => handleRowClick(member)}
            >
              <TableCell className="font-medium">
                {member.full_name ?? "\u2014"}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {member.email}
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  {member.roles.length > 0 ? (
                    member.roles.map((role) => {
                      const colorClass =
                        ROLE_COLORS[role.slug] ?? "bg-slate-100 text-slate-700";
                      return (
                        <span
                          key={role.id}
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
                        >
                          {ROLE_LABELS_RU[role.slug] ?? role.name}
                        </span>
                      );
                    })
                  ) : (
                    <span className="text-sm text-muted-foreground">\u2014</span>
                  )}
                </div>
              </TableCell>
              <TableCell>
                {member.status === "active" ? (
                  <Badge className="bg-green-100 text-green-700">
                    Активен
                  </Badge>
                ) : (
                  <Badge className="bg-red-100 text-red-700">
                    Заблокирован
                  </Badge>
                )}
              </TableCell>
              <TableCell>
                {member.telegram_username ? (
                  <span className="text-green-600 text-sm">
                    &#x2713; @{member.telegram_username}
                  </span>
                ) : (
                  <span className="text-muted-foreground">\u2014</span>
                )}
              </TableCell>
              <TableCell className="text-muted-foreground tabular-nums">
                {formatDate(member.joined_at)}
              </TableCell>
            </TableRow>
          ))}
          {filtered.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={6}
                className="text-center py-12 text-muted-foreground"
              >
                {search
                  ? "Ничего не найдено"
                  : "Нет пользователей"}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Create user dialog */}
      <CreateUserDialog
        allRoles={allRoles}
        salesGroups={salesGroups}
        open={isCreateDialogOpen}
        onOpenChange={setIsCreateDialogOpen}
      />

      {/* User edit sheet */}
      {selectedMember && (
        <UserEditSheet
          member={selectedMember}
          allRoles={allRoles}
          salesGroups={salesGroups}
          orgId={orgId}
          isOpen={isEditSheetOpen}
          onClose={handleEditSheetClose}
        />
      )}
    </div>
  );
}
