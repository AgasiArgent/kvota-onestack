import { LogoutButton } from "./logout-button";

/**
 * Testing 2 row 38p2 — placeholder shown to users whose only role is
 * `newbie` (a parking slot for inactive/unassigned employees). All
 * routes redirect here from app/(app)/layout.tsx, and the sidebar is
 * empty for these users. The page offers the user a way out by signing
 * out so a different account can be used.
 */
export default function AwaitingRolePage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="max-w-md w-full text-center space-y-4">
        <h1 className="text-2xl font-semibold">Ожидайте назначения роли</h1>
        <p className="text-sm text-muted-foreground">
          Обратитесь к вашему руководителю — РОП, РОЛ или РОЗ — чтобы
          назначить рабочую роль. После этого функционал станет доступен.
        </p>
        <LogoutButton />
      </div>
    </div>
  );
}
