import { notFound, redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { canSeeControlBoard } from "@/shared/lib/roles";
// Direct import from the server-only queries module (not the entity barrel) —
// the barrel re-exports only client-safe types, keeping fetchControlBoard out
// of any client bundle.
import { fetchControlBoard } from "@/entities/workspace-control/queries";
import { ControlWorkspace } from "@/features/workspace-control";

/**
 * /workspace/control — two control kanbans on one route (control-spec-workspace
 * Req 9).
 *
 * Mirrors workspace/logistics: getSessionUser → orgId redirect → role guard →
 * Promise.all of the two board fetches → render. Diverges from logistics in one
 * deliberate way: it is FAIL-CLOSED (Req 11.5). A user who can see neither board
 * (no quote_controller / spec_controller / admin / top_manager role) is sent to
 * notFound() — control queues must not be discoverable by unauthorized roles.
 */
export default async function WorkspaceControlPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  const orgId = user.orgId;

  const { calc, spec } = canSeeControlBoard(user.roles);

  // Fail-closed: neither board visible → 404 (deliberate divergence from the
  // fail-open logistics/customs pages).
  if (!calc && !spec) notFound();

  const fetchUser = { id: user.id, roles: user.roles, orgId };

  const [calcCards, specCards] = await Promise.all([
    calc ? fetchControlBoard("calc", fetchUser) : Promise.resolve(null),
    spec ? fetchControlBoard("spec", fetchUser) : Promise.resolve(null),
  ]);

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-text">
          Контроль
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Очередь контроля расчёта и спецификации
        </p>
      </header>

      <ControlWorkspace calcCards={calcCards} specCards={specCards} />
    </div>
  );
}
