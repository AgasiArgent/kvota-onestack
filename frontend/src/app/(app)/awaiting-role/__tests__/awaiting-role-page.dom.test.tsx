// @vitest-environment jsdom
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import AwaitingRolePage from "../page";

// next/navigation cannot be invoked inside a jsdom test without a fake
// Next.js router context — mock it so <LogoutButton /> can render.
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

// Supabase client is constructed inside the logout handler. We never
// click it in this test (the snapshot/heading test is enough), but the
// import needs to resolve.
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { signOut: vi.fn() },
  }),
}));

describe("AwaitingRolePage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the placeholder heading", () => {
    render(<AwaitingRolePage />);
    expect(
      screen.getByRole("heading", { name: /ожидайте назначения роли/i }),
    ).toBeInTheDocument();
  });

  it("instructs the user to contact their manager", () => {
    render(<AwaitingRolePage />);
    // Body copy mentions the РОП/РОЛ/РОЗ chain so the user knows who to ask.
    expect(
      screen.getByText(/обратитесь к вашему руководителю/i),
    ).toBeInTheDocument();
  });

  it("offers a sign-out button", () => {
    render(<AwaitingRolePage />);
    expect(
      screen.getByRole("button", { name: /выйти/i }),
    ).toBeInTheDocument();
  });
});
