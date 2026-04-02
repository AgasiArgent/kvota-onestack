import { type NextRequest, NextResponse } from "next/server";
import { updateSession } from "@/shared/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // Redirect /telegram → /profile#notifications
  if (pathname === "/telegram") {
    const url = request.nextUrl.clone();
    url.pathname = "/profile";
    url.hash = "notifications";
    return NextResponse.redirect(url);
  }

  // Default: run session update
  return updateSession(request);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
