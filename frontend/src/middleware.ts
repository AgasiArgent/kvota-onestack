import { type NextRequest, NextResponse } from "next/server";
import { updateSession } from "@/shared/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  // Redirect /telegram → /profile#notifications
  if (request.nextUrl.pathname === "/telegram") {
    const url = request.nextUrl.clone();
    url.pathname = "/profile";
    url.hash = "notifications";
    return NextResponse.redirect(url);
  }

  return await updateSession(request);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
