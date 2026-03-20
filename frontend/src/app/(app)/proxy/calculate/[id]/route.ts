import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const LEGACY_URL = process.env.NEXT_PUBLIC_LEGACY_APP_URL || "https://kvotaflow.ru";

export const dynamic = "force-dynamic";

/**
 * Proxy calculate request to Python backend.
 * Avoids CORS issues (app.kvotaflow.ru → kvotaflow.ru).
 * Next.js handles auth, then forwards form data to Python.
 */
export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await req.text();

  // Forward all cookies for session auth on the Python side
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  try {
    const res = await fetch(
      `${LEGACY_URL}/quotes/${id}/calculate`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          Cookie: cookieHeader,
        },
        body,
        redirect: "manual",
      }
    );

    // Python may return 303 redirect on success
    if (res.status === 303 || res.ok) {
      return NextResponse.json({ ok: true });
    }

    const text = await res.text();
    return NextResponse.json(
      { error: text || "Calculation failed" },
      { status: res.status }
    );
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to reach calculation engine" },
      { status: 502 }
    );
  }
}
