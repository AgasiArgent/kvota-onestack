import "server-only";

import { createServerClient } from "@supabase/ssr";
import { createClient as createJsClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import type { Database } from "@/shared/types/database.types";

// Share auth cookies across subdomains
const COOKIE_DOMAIN = process.env.NODE_ENV === "production" ? ".kvotaflow.ru" : undefined;

/**
 * Server-side Supabase client with user's auth context (via cookies).
 * Use for auth operations and user-scoped data queries.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      db: { schema: "kvota" },
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, {
                ...options,
                ...(COOKIE_DOMAIN ? { domain: COOKIE_DOMAIN } : {}),
              })
            );
          } catch {
            // The `setAll` method was called from a Server Component.
            // This can be ignored if you have middleware refreshing sessions.
          }
        },
      },
    }
  );
}

/**
 * Server-side admin client using service_role key (bypasses RLS).
 * Use ONLY in server code for internal lookups (roles, org membership)
 * after the user has been authenticated via auth.getUser().
 * Never expose this client or its key to the browser.
 */
export function createAdminClient() {
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!serviceRoleKey) {
    throw new Error("SUPABASE_SERVICE_ROLE_KEY is not set");
  }

  return createJsClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    serviceRoleKey,
    {
      db: { schema: "kvota" },
      auth: {
        autoRefreshToken: false,
        persistSession: false,
      },
    }
  );
}
