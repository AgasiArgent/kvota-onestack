// @vitest-environment jsdom
/**
 * Testing 2 (Denis, 2026-05-25) — when a user has only the `newbie`
 * parking role the (app) layout redirects them to `/awaiting-role`.
 * The tester complained that the destination page was a "white page
 * without buttons" with no way to log out — they could not even read
 * which account they were logged in as to ask an admin to reassign
 * them.
 *
 * This test pins the user-visible contract for the page:
 *
 *   1. A clear waiting message in Russian using the wording the
 *      tester requested («Ожидайте распределение», «ожидает
 *      распределение от админа или HR»).
 *   2. The current user's email is shown so they can identify
 *      themselves to whoever assigns roles.
 *   3. A «Выйти» button is visible. Clicking it calls Supabase
 *      `auth.signOut()` so the user can switch accounts.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import AwaitingRolePage from "../page";

// next/navigation cannot be invoked inside a jsdom test without a fake
// Next.js router context. Mock it so <LogoutButton /> can render and
// we can observe its post-signOut redirect call.
const pushMock = vi.fn();
const refreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    refresh: refreshMock,
  }),
}));

// Spy on Supabase signOut so the click assertion has something to
// observe. The actual network call must never happen in a unit test.
const signOutMock = vi.fn().mockResolvedValue({ error: null });
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { signOut: signOutMock },
  }),
}));

// `getSessionUser` reaches into the server-side Supabase admin client
// (cookies + DB lookups). In a jsdom unit test we substitute a
// deterministic stub so the assertion on the email line is reliable.
vi.mock("@/entities/user", () => ({
  getSessionUser: vi.fn().mockResolvedValue({
    id: "user-1",
    email: "newbie@example.com",
    orgId: "org-1",
    orgName: "Acme",
    roles: ["newbie"],
  }),
}));

async function renderPage() {
  // The page is an async Server Component — await the JSX it returns
  // before handing it to React Testing Library.
  const ui = await AwaitingRolePage();
  return render(ui as React.ReactElement);
}

describe("AwaitingRolePage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the «Ожидайте распределение» heading", async () => {
    await renderPage();
    expect(
      screen.getByRole("heading", { name: /ожидайте распределение/i }),
    ).toBeInTheDocument();
  });

  it("explains that the user is waiting for an admin or HR to assign access", async () => {
    await renderPage();
    expect(
      screen.getByText(
        /прав на доступ нет — ожидает распределение от админа или hr/i,
      ),
    ).toBeInTheDocument();
  });

  it("shows the current user's email so they can identify themselves", async () => {
    await renderPage();
    expect(screen.getByText(/newbie@example\.com/)).toBeInTheDocument();
  });

  it("offers a sign-out button that calls Supabase signOut on click", async () => {
    await renderPage();
    const button = screen.getByRole("button", { name: /выйти/i });
    expect(button).toBeInTheDocument();

    fireEvent.click(button);
    await waitFor(() => {
      expect(signOutMock).toHaveBeenCalledTimes(1);
    });
    // Confirm the user is redirected back to /login after signing out
    // so they can land somewhere usable (and not loop on /awaiting-role).
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/login");
    });
  });
});
