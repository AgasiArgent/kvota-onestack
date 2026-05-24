/**
 * Route shell for /kp-builder.
 *
 * The `(app)` segment layout already redirects unauthenticated users to
 * /login (REQ-1.4), so this page only renders for an authenticated
 * Supabase session. No role-based gating in iteration 1 (REQ-1.3).
 */

import { KpBuilderPage } from "@/views/kp-builder";

export default function Page() {
  return <KpBuilderPage />;
}
