import { NextResponse } from "next/server";
import { createAdminClient } from "@/shared/lib/supabase/server";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { first_name, last_name, email, phone, position, department, manager } = body;

    if (!first_name?.trim() || !last_name?.trim() || !email?.trim()) {
      return NextResponse.json(
        { success: false, error: "Имя, фамилия и email обязательны" },
        { status: 400 }
      );
    }

    const supabase = createAdminClient();

    // Table not yet in generated types — cast needed until `npm run db:types`
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const db = supabase as any;

    // Check for duplicate pending request with same email
    const { data: existing } = await db
      .from("registration_requests")
      .select("id")
      .eq("email", email.trim())
      .eq("status", "pending")
      .maybeSingle();

    if (existing) {
      return NextResponse.json(
        { success: false, error: "Заявка с таким email уже отправлена" },
        { status: 409 }
      );
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
      return NextResponse.json(
        { success: false, error: "Ошибка сохранения. Попробуйте ещё раз." },
        { status: 500 }
      );
    }

    // Send Telegram notification (fire and forget)
    sendTelegramNotification({ first_name, last_name, email, phone, position, department, manager });

    return NextResponse.json({ success: true });
  } catch {
    return NextResponse.json(
      { success: false, error: "Ошибка сервера" },
      { status: 500 }
    );
  }
}

async function sendTelegramNotification(data: {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  position?: string;
  department?: string;
  manager?: string;
}) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.ADMIN_TELEGRAM_CHAT_ID;

  if (!token || !chatId) return;

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

  try {
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: lines.join("\n"),
        parse_mode: "HTML",
      }),
    });
  } catch (e) {
    console.error("Telegram notification failed:", e);
  }
}
