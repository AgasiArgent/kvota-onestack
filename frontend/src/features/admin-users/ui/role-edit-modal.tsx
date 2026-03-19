"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { OrgMember, RoleOption } from "@/entities/admin/types";
import { ROLE_COLORS } from "@/entities/admin/types";
import { ROLE_LABELS_RU } from "@/entities/user/types";
import { updateUserRoles } from "@/entities/admin/mutations";

interface RoleEditModalProps {
  member: OrgMember;
  allRoles: RoleOption[];
  orgId: string;
  currentUserId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RoleEditModal({
  member,
  allRoles,
  orgId,
  currentUserId,
  open,
  onOpenChange,
}: RoleEditModalProps) {
  const router = useRouter();
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(
    new Set(member.roles.map((r) => r.slug))
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditingSelf = member.user_id === currentUserId;
  const canSave = selectedSlugs.size > 0;

  function handleToggle(slug: string, checked: boolean) {
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

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    setError(null);

    try {
      await updateUserRoles(member.user_id, orgId, Array.from(selectedSlugs));
      onOpenChange(false);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Ошибка при сохранении ролей"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Редактирование ролей</DialogTitle>
          <DialogDescription>
            {member.full_name ?? member.email} ({member.email})
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {allRoles.map((role) => {
            const isAdminForSelf =
              isEditingSelf && role.slug === "admin" && selectedSlugs.has("admin");
            const colorClass = ROLE_COLORS[role.slug] ?? "bg-slate-100 text-slate-700";

            return (
              <div key={role.id} className="flex items-center gap-3">
                <Checkbox
                  id={`role-${role.id}`}
                  checked={selectedSlugs.has(role.slug)}
                  onCheckedChange={(checked) =>
                    handleToggle(role.slug, checked === true)
                  }
                  disabled={isAdminForSelf}
                />
                <Label
                  htmlFor={`role-${role.id}`}
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

        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}

        {!canSave && (
          <p className="text-sm text-amber-600">
            Необходимо выбрать хотя бы одну роль
          </p>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Отмена
          </Button>
          <Button
            onClick={handleSave}
            disabled={!canSave || saving}
          >
            {saving ? "Сохранение..." : "Сохранить"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
