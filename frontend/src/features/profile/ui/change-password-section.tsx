"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { changePassword } from "@/entities/profile/mutations";

interface Props {
  email: string;
}

export function ChangePasswordSection({ email }: Props) {
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!current || !next || !confirm) {
      setError("Заполните все поля");
      return;
    }
    if (next.length < 8) {
      setError("Новый пароль должен быть не короче 8 символов");
      return;
    }
    if (next !== confirm) {
      setError("Пароли не совпадают");
      return;
    }
    if (next === current) {
      setError("Новый пароль совпадает с текущим");
      return;
    }

    setSaving(true);
    try {
      await changePassword(email, current, next);
      toast.success("Пароль изменён");
      setCurrent("");
      setNext("");
      setConfirm("");
      router.refresh();
    } catch (err) {
      if (err instanceof Error && err.message === "CURRENT_PASSWORD_INVALID") {
        setError("Неверный текущий пароль");
      } else {
        toast.error("Не удалось сменить пароль");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Смена пароля</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-sm">
          <div className="space-y-1.5">
            <Label htmlFor="cp-current">Текущий пароль</Label>
            <Input
              id="cp-current"
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cp-next">Новый пароль</Label>
            <Input
              id="cp-next"
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cp-confirm">Повторите новый пароль</Label>
            <Input
              id="cp-confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button
            type="submit"
            disabled={saving}
            className="self-start bg-accent text-white hover:bg-accent-hover"
          >
            {saving ? "Сохранение..." : "Сменить пароль"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
