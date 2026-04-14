"use server";

import { createAdminClient } from "@/shared/lib/supabase/server";

interface RegistrationInput {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  position?: string;
  department?: string;
  manager?: string;
}

export async function submitRegistration(
  input: RegistrationInput
): Promise<{ success: boolean; error?: string }> {
  const { first_name, last_name, email, phone, position, department, manager } =
    input;

  if (!first_name?.trim() || !last_name?.trim() || !email?.trim()) {
    return { success: false, error: "Имя, фамилия и email обязательны" };
  }

  // Table not yet in generated types — cast needed until `npm run db:types`
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const db = createAdminClient() as any;

  // Check for duplicate pending request
  const { data: existing } = await db
    .from("registration_requests")
    .select("id")
    .eq("email", email.trim())
    .eq("status", "pending")
    .maybeSingle();

  if (existing) {
    return { success: false, error: "Заявка с таким email уже отправлена" };
  }

  const { error: insertError } = await db
    .from("registration_requests")
    .insert({
      first_name: first_name.trim(),
      last_name: last_name.trim(),
      email: email.trim(),
      phone: phone?.trim() || null,
      position: position?.trim() || null,
      department: department?.trim() || null,
      manager: manager?.trim() || null,
    });

  if (insertError) {
    console.error("Registration insert failed:", insertError);
    return { success: false, error: "Ошибка сохранения. Попробуйте ещё раз." };
  }

  // Send Telegram notification (fire and forget)
  sendTelegramNotification({
    first_name,
    last_name,
    email,
    phone,
    position,
    department,
    manager,
  }).catch((e) => console.error("Telegram notification failed:", e));

  return { success: true };
}

async function sendTelegramNotification(data: RegistrationInput) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  // Multi-chat support: prefer ADMIN_TELEGRAM_CHAT_IDS (comma-separated).
  // Fallback to ADMIN_TELEGRAM_CHAT_ID for backwards compatibility.
  const rawChatIds =
    process.env.ADMIN_TELEGRAM_CHAT_IDS ??
    process.env.ADMIN_TELEGRAM_CHAT_ID ??
    "";
  const chatIds = rawChatIds
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  if (!token || chatIds.length === 0) return;

  const lines = [
    `📋 <b>Новая заявка на регистрацию</b>`,
    ``,
    `👤 ${data.first_name} ${data.last_name}`,
    `📧 ${data.email}`,
  ];
  if (data.phone) lines.push(`📱 ${data.phone}`);
  if (data.position) lines.push(`💼 ${data.position}`);
  if (data.department) lines.push(`🏢 ${data.department}`);
  if (data.manager) lines.push(`👔 Руководитель: ${data.manager}`);

  const text = lines.join("\n");

  const results = await Promise.allSettled(
    chatIds.map(async (chat_id) => {
      const res = await fetch(
        `https://api.telegram.org/bot${token}/sendMessage`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id, text, parse_mode: "HTML" }),
        }
      );
      // Telegram returns 400/403/429 for chat-not-found, bot-blocked, rate-limit.
      // These are fulfilled HTTP responses — must throw to surface in allSettled.
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`Telegram HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      return res;
    })
  );

  results.forEach((r, i) => {
    if (r.status === "rejected") {
      console.error(
        `Telegram notify failed for chat_id=${chatIds[i]}:`,
        r.reason
      );
    }
  });
}
