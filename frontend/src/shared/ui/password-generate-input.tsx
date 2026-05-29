"use client";

import { Copy, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { generatePassword } from "@/shared/lib/password";

interface PasswordGenerateInputProps {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  placeholder?: string;
  error?: boolean;
  autoFocus?: boolean;
}

/**
 * Controlled password field with generate (↻) and copy (⧉) buttons. Shared by
 * the admin create-user dialog and the admin password-reset section.
 */
export function PasswordGenerateInput({
  value,
  onChange,
  id,
  placeholder = "Минимум 8 символов",
  error = false,
  autoFocus = false,
}: PasswordGenerateInputProps) {
  async function handleCopy() {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      toast.success("Пароль скопирован");
    } catch {
      toast.error("Не удалось скопировать");
    }
  }

  return (
    <div className="flex gap-2">
      <Input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        className={`flex-1 ${error ? "border-destructive" : ""}`}
      />
      <Button
        type="button"
        variant="outline"
        size="default"
        onClick={() => onChange(generatePassword())}
        title="Сгенерировать пароль"
      >
        <RefreshCw size={14} />
      </Button>
      <Button
        type="button"
        variant="outline"
        size="default"
        onClick={handleCopy}
        disabled={!value}
        title="Скопировать пароль"
      >
        <Copy size={14} />
      </Button>
    </div>
  );
}
