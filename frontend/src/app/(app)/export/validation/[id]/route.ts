import { NextResponse } from "next/server";
import { createClient } from "@/shared/lib/supabase/server";
import { config } from "@/shared/config";

/**
 * Validation Excel proxy route.
 *
 * Forwards GET /export/validation/{id} to the Python API at
 * /api/quotes/{id}/export/validation. The Python handler does the heavy
 * lifting (fetch_export_data + create_validation_excel); we only forward
 * the Supabase JWT and stream the xlsm bytes back to the browser.
 *
 * Replaces the dead FastHTML route at `${legacyAppUrl}/quotes/{id}/export/validation`
 * (archived 2026-04-20 in Phase 6C-2B-Mega-C).
 */

export const dynamic = "force-dynamic";

const DEFAULT_MEDIA_TYPE = "application/vnd.ms-excel.sheet.macroEnabled.12";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const upstream = await fetch(
    `${config.pythonApiUrl}/api/quotes/${id}/export/validation`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
      },
      cache: "no-store",
    },
  );

  const buffer = await upstream.arrayBuffer();
  const contentType = upstream.headers.get("Content-Type") ?? DEFAULT_MEDIA_TYPE;
  const contentDisposition =
    upstream.headers.get("Content-Disposition") ??
    `attachment; filename="validation_${id}.xlsm"`;

  return new NextResponse(buffer, {
    status: upstream.status,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": contentDisposition,
    },
  });
}
