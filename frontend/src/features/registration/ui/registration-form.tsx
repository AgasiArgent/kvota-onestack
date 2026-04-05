"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Layers, UserPlus, CheckCircle2 } from "lucide-react";
import { submitRegistration } from "../actions";

interface FormData {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  position: string;
  department: string;
  manager: string;
}

const INITIAL: FormData = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  position: "",
  department: "",
  manager: "",
};

export function RegistrationForm() {
  const [form, setForm] = useState<FormData>(INITIAL);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  function update(field: keyof FormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await submitRegistration(form);

      if (!result.success) {
        setError(result.error ?? "Ошибка отправки");
        return;
      }

      setSubmitted(true);
    } catch {
      setError("Ошибка соединения. Попробуйте ещё раз.");
    } finally {
      setLoading(false);
    }
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-background">
        <Card className="w-full max-w-[420px] shadow-lg">
          <CardContent className="text-center py-10 space-y-4">
            <div className="mx-auto w-14 h-14 bg-green-100 rounded-full flex items-center justify-center">
              <CheckCircle2 className="text-green-600" size={28} />
            </div>
            <h2 className="text-xl font-semibold">Заявка отправлена</h2>
            <p className="text-sm text-muted-foreground">
              Администратор создаст вам учётную запись и пришлёт данные для входа.
            </p>
            <Link
              href="/login"
              className="inline-flex items-center text-sm text-accent hover:underline"
            >
              Вернуться к входу
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <Card className="w-full max-w-[480px] shadow-lg">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-14 h-14 bg-accent rounded-lg flex items-center justify-center shadow-md">
            <Layers className="text-white" size={28} />
          </div>
          <div>
            <CardTitle className="text-2xl font-bold tracking-tight">
              Регистрация
            </CardTitle>
            <CardDescription>
              Заполните форму — администратор создаст вам учётную запись
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name row */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="first_name">Имя *</Label>
                <Input
                  id="first_name"
                  value={form.first_name}
                  onChange={(e) => update("first_name", e.target.value)}
                  placeholder="Иван"
                  required
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="last_name">Фамилия *</Label>
                <Input
                  id="last_name"
                  value={form.last_name}
                  onChange={(e) => update("last_name", e.target.value)}
                  placeholder="Петров"
                  required
                />
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="email">Email *</Label>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                placeholder="ivan.petrov@company.ru"
                required
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="phone">Телефон</Label>
              <Input
                id="phone"
                type="tel"
                value={form.phone}
                onChange={(e) => update("phone", e.target.value)}
                placeholder="+7 999 123-45-67"
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="position">Должность</Label>
              <Input
                id="position"
                value={form.position}
                onChange={(e) => update("position", e.target.value)}
                placeholder="Менеджер по закупкам"
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="department">Департамент</Label>
              <Input
                id="department"
                value={form.department}
                onChange={(e) => update("department", e.target.value)}
                placeholder="Отдел закупок"
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="manager">Руководитель</Label>
              <Input
                id="manager"
                value={form.manager}
                onChange={(e) => update("manager", e.target.value)}
                placeholder="ФИО руководителя"
              />
            </div>

            {error && (
              <p className="text-sm text-error bg-error-bg px-3 py-2 rounded-md">
                {error}
              </p>
            )}

            <Button
              type="submit"
              className="w-full bg-accent text-white hover:bg-accent-hover"
              disabled={loading}
            >
              <UserPlus size={18} />
              {loading ? "Отправка..." : "Отправить заявку"}
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              Уже есть аккаунт?{" "}
              <Link href="/login" className="text-accent hover:underline">
                Войти
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
