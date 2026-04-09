"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { OrgMember, RoleOption } from "@/entities/admin/types";
import { ROLE_COLORS } from "@/entities/admin/types";
import { ROLE_LABELS_RU } from "@/entities/user/types";
import { updateUserProfile } from "@/entities/admin/mutations";
import {
  updateUserRolesAction,
  updateUserStatusAction,
} from "@/features/admin-users/actions";

const SALES_ROLE_SLUGS = new Set(["sales", "head_of_sales"]);

interface SalesGroupOption {
  id: string;
  name: string;
}

interface DepartmentOption {
  id: string;
  name: string;
}

interface UserEditSheetProps {
  member: OrgMember;
  allRoles: RoleOption[];
  salesGroups: SalesGroupOption[];
  departments: DepartmentOption[];
  orgId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function UserEditSheet({
  member,
  allRoles,
  salesGroups,
  departments,
  orgId,
  isOpen,
  onClose,
}: UserEditSheetProps) {
  const router = useRouter();

  // Profile state
  const [fullName, setFullName] = useState(member.full_name ?? "");
  const [position, setPosition] = useState(member.position ?? "");
  const [salesGroupId, setSalesGroupId] = useState(
    member.sales_group_id ?? ""
  );
  const [departmentId, setDepartmentId] = useState(
    member.department_id ?? ""
  );
  const [savingProfile, setSavingProfile] = useState(false);

  // Roles state
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(
    new Set(member.roles.map((r) => r.slug))
  );
  const [savingRoles, setSavingRoles] = useState(false);

  // Status state
  const [confirmDeactivateOpen, setConfirmDeactivateOpen] = useState(false);
  const [savingStatus, setSavingStatus] = useState(false);

  const isActive = member.status !== "suspended";
  const isLastAdmin =
    member.roles.some((r) => r.slug === "admin") && member.is_last_admin;
  const hasSalesRole = Array.from(selectedSlugs).some((s) =>
    SALES_ROLE_SLUGS.has(s)
  );

  // Reset state when member changes
  useEffect(() => {
    setFullName(member.full_name ?? "");
    setPosition(member.position ?? "");
    setSalesGroupId(member.sales_group_id ?? "");
    setDepartmentId(member.department_id ?? "");
    setSelectedSlugs(new Set(member.roles.map((r) => r.slug)));
  }, [member]);

  async function handleSaveProfile() {
    if (!fullName.trim()) {
      toast.error("ФИО не может быть пустым");
      return;
    }

    setSavingProfile(true);
    try {
      const { error } = await updateUserProfile(member.user_id, orgId, {
        full_name: fullName.trim(),
        position: position.trim() || null,
        sales_group_id:
          hasSalesRole && salesGroupId ? salesGroupId : null,
        department_id: departmentId || null,
      });

      if (error) throw error;

      toast.success("Профиль обновлён");
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка сохранения профиля";
      toast.error(message);
    } finally {
      setSavingProfile(false);
    }
  }

  function handleToggleRole(slug: string, checked: boolean) {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(slug);
      } else {
        next.delete(slug);
      }
      return next;
    });
  }

  async function handleSaveRoles() {
    if (selectedSlugs.size === 0) {
      toast.error("Необходимо выбрать хотя бы одну роль");
      return;
    }

    setSavingRoles(true);
    try {
      const res = await updateUserRolesAction(
        member.user_id,
        Array.from(selectedSlugs)
      );

      if (res.success) {
        toast.success("Роли обновлены");
        router.refresh();
      } else {
        const errorMessage =
          res.error?.code === "LAST_ADMIN"
            ? "Невозможно удалить роль admin у последнего администратора"
            : res.error?.message ?? "Ошибка обновления ролей";
        toast.error(errorMessage);
      }
    } catch {
      toast.error("Ошибка обновления ролей");
    } finally {
      setSavingRoles(false);
    }
  }

  async function handleStatusChange(newStatus: "active" | "suspended") {
    setSavingStatus(true);
    setConfirmDeactivateOpen(false);

    try {
      const res = await updateUserStatusAction(member.user_id, newStatus);

      if (res.success) {
        toast.success(
          newStatus === "active"
            ? "Пользователь активирован"
            : "Пользователь деактивирован"
        );
        onClose();
        router.refresh();
      } else {
        const errorMessage =
          res.error?.code === "LAST_ADMIN"
            ? "Невозможно деактивировать последнего администратора"
            : res.error?.message ?? "Ошибка изменения статуса";
        toast.error(errorMessage);
      }
    } catch {
      toast.error("Ошибка изменения статуса");
    } finally {
      setSavingStatus(false);
    }
  }

  const rolesChanged =
    selectedSlugs.size !== member.roles.length ||
    !member.roles.every((r) => selectedSlugs.has(r.slug));

  return (
    <>
      <Sheet open={isOpen} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
        <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{member.full_name ?? member.email}</SheetTitle>
            <SheetDescription>{member.email}</SheetDescription>
          </SheetHeader>

          <div className="flex flex-col gap-6 px-4 pb-4">
            {/* Section: Profile */}
            <section className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Профиль
              </h3>

              <div className="flex flex-col gap-1.5">
                <Label
                  htmlFor="edit-user-name"
                  className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  ФИО
                </Label>
                <Input
                  id="edit-user-name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Иванов Иван Иванович"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label
                  htmlFor="edit-user-position"
                  className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  Должность
                </Label>
                <Input
                  id="edit-user-position"
                  value={position}
                  onChange={(e) => setPosition(e.target.value)}
                  placeholder="Менеджер по продажам"
                />
              </div>

              {hasSalesRole && salesGroups.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Группа продаж
                  </Label>
                  <Select value={salesGroupId} onValueChange={(val) => setSalesGroupId(val ?? "")}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Выберите группу" />
                    </SelectTrigger>
                    <SelectContent>
                      {salesGroups.map((group) => (
                        <SelectItem key={group.id} value={group.id}>
                          {group.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {departments.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Департамент
                  </Label>
                  <Select value={departmentId} onValueChange={(val) => setDepartmentId(val ?? "")}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Выберите департамент" />
                    </SelectTrigger>
                    <SelectContent>
                      {departments.map((dept) => (
                        <SelectItem key={dept.id} value={dept.id}>
                          {dept.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <Button
                onClick={handleSaveProfile}
                disabled={savingProfile}
                size="sm"
                className="self-end"
              >
                {savingProfile && (
                  <Loader2 size={14} className="animate-spin" />
                )}
                Сохранить профиль
              </Button>
            </section>

            <Separator />

            {/* Section: Roles */}
            <section className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Роли
              </h3>

              <div className="space-y-2">
                {allRoles.map((role) => {
                  const colorClass =
                    ROLE_COLORS[role.slug] ?? "bg-slate-100 text-slate-700";
                  const isAdminLastGuard =
                    isLastAdmin && role.slug === "admin";

                  return (
                    <div key={role.id} className="flex items-center gap-3">
                      <Checkbox
                        id={`edit-role-${role.id}`}
                        checked={selectedSlugs.has(role.slug)}
                        onCheckedChange={(checked) =>
                          handleToggleRole(role.slug, checked === true)
                        }
                        disabled={isAdminLastGuard}
                      />
                      <Label
                        htmlFor={`edit-role-${role.id}`}
                        className="flex items-center gap-2 cursor-pointer"
                      >
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colorClass}`}
                        >
                          {ROLE_LABELS_RU[role.slug] ?? role.name}
                        </span>
                      </Label>
                    </div>
                  );
                })}
              </div>

              {selectedSlugs.size === 0 && (
                <p className="text-xs text-amber-600">
                  Необходимо выбрать хотя бы одну роль
                </p>
              )}

              <Button
                onClick={handleSaveRoles}
                disabled={
                  savingRoles || selectedSlugs.size === 0 || !rolesChanged
                }
                size="sm"
                className="self-end"
              >
                {savingRoles && (
                  <Loader2 size={14} className="animate-spin" />
                )}
                Сохранить роли
              </Button>
            </section>

            <Separator />

            {/* Section: Status */}
            <section className="flex flex-col gap-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Статус
              </h3>

              <div className="flex items-center gap-3">
                {isActive ? (
                  <Badge className="bg-green-100 text-green-700">
                    Активен
                  </Badge>
                ) : (
                  <Badge className="bg-red-100 text-red-700">
                    Заблокирован
                  </Badge>
                )}
              </div>

              {isActive ? (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setConfirmDeactivateOpen(true)}
                  disabled={savingStatus || isLastAdmin}
                  className="self-start"
                >
                  {savingStatus && (
                    <Loader2 size={14} className="animate-spin" />
                  )}
                  Деактивировать
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleStatusChange("active")}
                  disabled={savingStatus}
                  className="self-start"
                >
                  {savingStatus && (
                    <Loader2 size={14} className="animate-spin" />
                  )}
                  Активировать
                </Button>
              )}

              {isLastAdmin && isActive && (
                <p className="text-xs text-muted-foreground">
                  Невозможно деактивировать последнего администратора
                </p>
              )}
            </section>
          </div>
        </SheetContent>
      </Sheet>

      {/* Confirm deactivation dialog */}
      <Dialog
        open={confirmDeactivateOpen}
        onOpenChange={setConfirmDeactivateOpen}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Деактивация пользователя</DialogTitle>
            <DialogDescription>
              Пользователь {member.full_name ?? member.email} будет
              заблокирован и не сможет войти в систему. Это действие можно
              отменить.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmDeactivateOpen(false)}
            >
              Отмена
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleStatusChange("suspended")}
              disabled={savingStatus}
            >
              {savingStatus && (
                <Loader2 size={14} className="animate-spin" />
              )}
              Деактивировать
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
