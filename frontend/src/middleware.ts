import { type NextRequest, NextResponse } from "next/server";
import { updateSession } from "@/shared/lib/supabase/middleware";

const PHMB_HOST = "phmb.kvotaflow.ru";
const MAIN_HOST = "app.kvotaflow.ru";

function isPhmb(hostname: string): boolean {
  if (process.env.NEXT_PUBLIC_APP_CONTEXT === "phmb") return true;
  return hostname === PHMB_HOST || hostname.startsWith("phmb.");
}

export async function middleware(request: NextRequest) {
  const hostname = request.headers.get("host")?.split(":")[0] ?? "";
  const phmb = isPhmb(hostname);
  const pathname = request.nextUrl.pathname;

  // Redirect /telegram → /profile#notifications (any domain)
  if (pathname === "/telegram") {
    const url = request.nextUrl.clone();
    url.pathname = "/profile";
    url.hash = "notifications";
    return NextResponse.redirect(url);
  }

  // Main domain: redirect /phmb/* to PHMB subdomain
  if (!phmb && hostname === MAIN_HOST && pathname.startsWith("/phmb")) {
    const url = new URL(pathname, `https://${PHMB_HOST}`);
    url.search = request.nextUrl.search;
    return NextResponse.redirect(url);
  }

  // PHMB domain: redirect non-PHMB paths to main app
  if (phmb) {
    const phmbPaths = ["/phmb", "/login", "/profile", "/api", "/auth"];
    const isPhmbPath = phmbPaths.some((p) => pathname === p || pathname.startsWith(p + "/"));
    if (!isPhmbPath && pathname !== "/") {
      const url = new URL(pathname, `https://${MAIN_HOST}`);
      url.search = request.nextUrl.search;
      return NextResponse.redirect(url);
    }
  }

  // For PHMB root "/" → rewrite to /phmb (internal rewrite, not redirect)
  if (phmb && pathname === "/") {
    const url = request.nextUrl.clone();
    url.pathname = "/phmb";
    const response = NextResponse.rewrite(url);
    response.headers.set("x-app-context", "phmb");
    return response;
  }

  // Default: run session update and set app context
  const response = await updateSession(request);
  if (response) {
    response.headers.set("x-app-context", phmb ? "phmb" : "main");
  }
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
