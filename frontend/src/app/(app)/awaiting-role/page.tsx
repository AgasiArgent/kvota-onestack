import { Hourglass } from "lucide-react";
import { getSessionUser } from "@/entities/user";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { LogoutButton } from "./logout-button";

/**
 * Testing 2 row 38p2 — placeholder shown to users whose only role is
 * `newbie` (a parking slot for inactive/unassigned employees). All
 * `(app)/*` routes redirect here from `app/(app)/layout.tsx`, and the
 * sidebar nav is empty for these users. The page offers them a clear
 * waiting message, their own email (so they can identify themselves
 * to an administrator), and a logout button so they can switch
 * accounts without contacting support.
 */
export default async function AwaitingRolePage() {
  // The (app) layout already gated this route — a newbie-only user
  // cannot reach it without a session — but we still defensively
  // handle a missing user so the page never crashes.
  const user = await getSessionUser();

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <Card className="w-full max-w-md text-center">
        <CardHeader className="items-center gap-3">
          <div
            aria-hidden="true"
            className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-accent-subtle text-accent"
          >
            <Hourglass size={24} />
          </div>
          <h1 className="text-xl font-semibold leading-snug">
            Ожидайте распределение
          </h1>
          <p className="text-sm text-muted-foreground">
            Прав на доступ нет — ожидает распределение от админа или HR.
          </p>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4">
          {user?.email ? (
            <p className="text-xs text-text-subtle">
              Вы вошли как{" "}
              <span className="font-medium text-text-muted">{user.email}</span>
            </p>
          ) : null}
          <LogoutButton />
        </CardContent>
      </Card>
    </div>
  );
}
