"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Copy, RefreshCw } from "lucide-react";
import { toast } from "sonner";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { RoleOption } from "@/entities/admin/types";
import { ROLE_COLORS } from "@/entities/admin/types";
import { ROLE_LABELS_RU } from "@/entities/user/types";
import { createUserAction } from "@/features/admin-users/actions";

const SALES_ROLE_SLUGS = new Set(["sales", "head_of_sales"]);

interface SalesGroupOption {
  id: string;
  name: string;
}

interface CreateUserDialogProps {
  allRoles: RoleOption[];
  salesGroups: SalesGroupOption[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function generatePassword(): string {
  const chars =
    "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%";
  const array = new Uint8Array(12);
  crypto.getRandomValues(array);
  return Array.from(array, (byte) => chars[byte % chars.length]).join("");
}

function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

interface FormErrors {
  email?: string;
  password?: string;
  full_name?: string;
  roles?: string;
}

export function CreateUserDialog({
  allRoles,
  salesGroups,
  open,
  onOpenChange,
}: CreateUserDialogProps) {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [position, setPosition] = useState("");
  const [salesGroupId, setSalesGroupId] = useState<string>("");
  const [selectedSlugs, setSelectedSlugs] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const hasSalesRole = Array.from(selectedSlugs).some((s) =>
    SALES_ROLE_SLUGS.has(s)
  );

  useEffect(() => {
    if (open) {
      setEmail("");
      setPassword("");
      setFullName("");
      setPosition("");
      setSalesGroupId("");
      setSelectedSlugs(new Set());
      setErrors({});
      setSubmitting(false);
      setServerError(null);
    }
  }, [open]);

  useEffect(() => {
    if (!hasSalesRole) {
      setSalesGroupId("");
    }
  }, [hasSalesRole]);

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
    if (errors.roles) {
      setErrors((prev) => ({ ...prev, roles: undefined }));
    }
  }

  function handleGeneratePassword() {
    const pwd = generatePassword();
    setPassword(pwd);
    if (errors.password) {
      setErrors((prev) => ({ ...prev, password: undefined }));
    }
  }

  async function handleCopyPassword() {
    if (!password) return;
    try {
      await navigator.clipboard.writeText(password);
      toast.success("Пароль скопирован");
    } catch {
      toast.error("Не удалось скопировать");
    }
  }

  function validate(): FormErrors {
    const errs: FormErrors = {};
    if (!email.trim() || !validateEmail(email.trim())) {
      errs.email = "Введите корректный email";
    }
    if (!password || password.length < 8) {
      errs.password = "Минимум 8 символов";
    }
    if (!fullName.trim()) {
      errs.full_name = "Введите ФИО";
    }
    if (selectedSlugs.size === 0) {
      errs.roles = "Выберите хотя бы одну роль";
    }
    return errs;
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setServerError(null);
    setSubmitting(true);

    try {
      const res = await createUserAction({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        role_slugs: Array.from(selectedSlugs),
        position: position.trim() || undefined,
        sales_group_id: hasSalesRole && salesGroupId ? salesGroupId : undefined,
      });

      if (res.success) {
        onOpenChange(false);
        toast.success("Пользователь создан");
        router.refresh();
      } else {
        const errorMessage =
          res.error?.code === "USER_EXISTS"
            ? "Пользователь с таким email уже существует"
            : res.error?.message ?? "Ошибка создания пользователя";
        setServerError(errorMessage);
      }
    } catch {
      setServerError("Ошибка создания пользователя");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Добавить пользователя</DialogTitle>
          <DialogDescription>
            Заполните данные нового пользователя
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Email */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="create-user-email"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Email <span className="text-destructive">*</span>
            </Label>
            <Input
              id="create-user-email"
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (errors.email)
                  setErrors((prev) => ({ ...prev, email: undefined }));
              }}
              placeholder="user@example.com"
              autoFocus
              className={errors.email ? "border-destructive" : ""}
            />
            {errors.email && (
              <p className="text-xs text-destructive">{errors.email}</p>
            )}
          </fieldset>

          {/* Password */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="create-user-password"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Пароль <span className="text-destructive">*</span>
            </Label>
            <div className="flex gap-2">
              <Input
                id="create-user-password"
                type="text"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (errors.password)
                    setErrors((prev) => ({ ...prev, password: undefined }));
                }}
                placeholder="Минимум 8 символов"
                className={`flex-1 ${errors.password ? "border-destructive" : ""}`}
              />
              <Button
                type="button"
                variant="outline"
                size="default"
                onClick={handleGeneratePassword}
                title="Сгенерировать пароль"
              >
                <RefreshCw size={14} />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="default"
                onClick={handleCopyPassword}
                disabled={!password}
                title="Скопировать пароль"
              >
                <Copy size={14} />
              </Button>
            </div>
            {errors.password && (
              <p className="text-xs text-destructive">{errors.password}</p>
            )}
          </fieldset>

          {/* Full name */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="create-user-name"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              ФИО <span className="text-destructive">*</span>
            </Label>
            <Input
              id="create-user-name"
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value);
                if (errors.full_name)
                  setErrors((prev) => ({ ...prev, full_name: undefined }));
              }}
              placeholder="Иванов Иван Иванович"
              className={errors.full_name ? "border-destructive" : ""}
            />
            {errors.full_name && (
              <p className="text-xs text-destructive">{errors.full_name}</p>
            )}
          </fieldset>

          {/* Roles */}
          <fieldset className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Роли <span className="text-destructive">*</span>
            </Label>
            <div className="space-y-2 rounded-md border p-3">
              {allRoles.map((role) => {
                const colorClass =
                  ROLE_COLORS[role.slug] ?? "bg-slate-100 text-slate-700";
                return (
                  <div key={role.id} className="flex items-center gap-3">
                    <Checkbox
                      id={`create-role-${role.id}`}
                      checked={selectedSlugs.has(role.slug)}
                      onCheckedChange={(checked) =>
                        handleToggleRole(role.slug, checked === true)
                      }
                    />
                    <Label
                      htmlFor={`create-role-${role.id}`}
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
            {errors.roles && (
              <p className="text-xs text-destructive">{errors.roles}</p>
            )}
          </fieldset>

          {/* Position */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="create-user-position"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Должность
            </Label>
            <Input
              id="create-user-position"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              placeholder="Менеджер по продажам"
            />
          </fieldset>

          {/* Sales group (conditional) */}
          {hasSalesRole && salesGroups.length > 0 && (
            <fieldset className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
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
            </fieldset>
          )}

          {/* Server error */}
          {serverError && (
            <div className="rounded-md border border-destructive/50 bg-destructive/5 p-3">
              <p className="text-sm text-destructive">{serverError}</p>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Отмена
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Создать
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
