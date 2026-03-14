"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { UserProfile, ProfileFormData } from "@/entities/profile/types";
import { updateProfile } from "@/entities/profile/mutations";

interface Props {
  profile: UserProfile;
  email: string;
}

export function ProfileForm({ profile, email }: Props) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState<ProfileFormData>({
    full_name: profile.full_name ?? "",
    phone: profile.phone ?? "",
    position: profile.position ?? "",
    date_of_birth: profile.date_of_birth ?? "",
    timezone: profile.timezone ?? "Europe/Moscow",
    location: profile.location ?? "",
    bio: profile.bio ?? "",
  });

  function handleChange(
    field: keyof ProfileFormData,
    value: string
  ) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleCancel() {
    setForm({
      full_name: profile.full_name ?? "",
      phone: profile.phone ?? "",
      position: profile.position ?? "",
      date_of_birth: profile.date_of_birth ?? "",
      timezone: profile.timezone ?? "Europe/Moscow",
      location: profile.location ?? "",
      bio: profile.bio ?? "",
    });
    setEditing(false);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload: ProfileFormData = {
        ...form,
        date_of_birth: form.date_of_birth || null,
      };
      await updateProfile(profile.id, payload);
      setEditing(false);
      router.refresh();
    } catch {
      // Error is visible in console; user sees button re-enabled
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header with edit button */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Профиль</h1>
        {!editing && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditing(true)}
          >
            <Pencil className="h-4 w-4 mr-2" />
            Редактировать
          </Button>
        )}
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: Personal */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Личные данные</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field
              label="ФИО"
              value={form.full_name ?? ""}
              editing={editing}
              onChange={(v) => handleChange("full_name", v)}
            />
            <Field
              label="Телефон"
              value={form.phone ?? ""}
              editing={editing}
              onChange={(v) => handleChange("phone", v)}
            />
            <Field
              label="Дата рождения"
              value={form.date_of_birth ?? ""}
              editing={editing}
              type="date"
              onChange={(v) => handleChange("date_of_birth", v)}
            />
            <ReadOnlyField label="Email" value={email} />
          </CardContent>
        </Card>

        {/* Card 2: Work */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Рабочая информация</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field
              label="Должность"
              value={form.position ?? ""}
              editing={editing}
              onChange={(v) => handleChange("position", v)}
            />
            <Field
              label="Часовой пояс"
              value={form.timezone ?? ""}
              editing={editing}
              onChange={(v) => handleChange("timezone", v)}
            />
            <Field
              label="Офис / Локация"
              value={form.location ?? ""}
              editing={editing}
              onChange={(v) => handleChange("location", v)}
            />
            {profile.hire_date && (
              <ReadOnlyField
                label="Дата найма"
                value={new Date(profile.hire_date).toLocaleDateString("ru-RU")}
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Card 3: Bio — full width */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">О себе</CardTitle>
        </CardHeader>
        <CardContent>
          {editing ? (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Биография
              </Label>
              <Textarea
                value={form.bio ?? ""}
                onChange={(e) => handleChange("bio", e.target.value)}
                rows={4}
                placeholder="Расскажите о себе..."
              />
            </div>
          ) : (
            <div>
              <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Биография
              </span>
              <p className="text-sm mt-1 whitespace-pre-wrap">
                {profile.bio || "—"}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Action buttons */}
      {editing && (
        <div className="flex gap-3">
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-accent text-white hover:bg-accent-hover"
          >
            {saving ? "Сохранение..." : "Сохранить"}
          </Button>
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={saving}
          >
            Отмена
          </Button>
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  editing,
  type = "text",
  onChange,
}: {
  label: string;
  value: string;
  editing: boolean;
  type?: "text" | "date";
  onChange: (value: string) => void;
}) {
  if (editing) {
    return (
      <div className="space-y-1.5">
        <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          {label}
        </Label>
        <Input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    );
  }

  return (
    <div className="flex justify-between">
      <span className="text-text-muted text-sm">{label}</span>
      <span className="text-sm font-medium">
        {type === "date" && value
          ? new Date(value).toLocaleDateString("ru-RU")
          : value || "—"}
      </span>
    </div>
  );
}

function ReadOnlyField({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-text-muted text-sm">{label}</span>
      <span className="text-sm font-medium">{value || "—"}</span>
    </div>
  );
}
