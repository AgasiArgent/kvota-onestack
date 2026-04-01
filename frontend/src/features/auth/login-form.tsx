"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/shared/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Layers, LogIn } from "lucide-react";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const supabase = createClient();
      const { error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (authError) {
        setError(
          authError.message.includes("Invalid login credentials")
            ? "Неверный email или пароль"
            : authError.message
        );
        return;
      }

      router.push("/quotes");
      router.refresh();
    } catch {
      setError("Ошибка соединения. Попробуйте ещё раз.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <Card className="w-full max-w-[420px] shadow-lg">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-14 h-14 bg-accent rounded-lg flex items-center justify-center shadow-md">
            <Layers className="text-white" size={28} />
          </div>
          <div>
            <CardTitle className="text-2xl font-bold tracking-tight">OneStack</CardTitle>
            <CardDescription>Система управления коммерческими предложениями</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1">
              <Label htmlFor="email" className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Электронная почта
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password" className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Пароль
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <p className="text-sm text-error bg-error-bg px-3 py-2 rounded-md">{error}</p>
            )}
            <Button type="submit" className="w-full bg-accent text-white hover:bg-accent-hover" disabled={loading}>
              <LogIn size={18} />
              {loading ? "Вход..." : "Войти в систему"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              Нет аккаунта?{" "}
              <Link href="/register" className="text-accent hover:underline">
                Оставить заявку
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
