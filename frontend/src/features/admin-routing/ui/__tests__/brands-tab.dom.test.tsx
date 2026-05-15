// @vitest-environment jsdom
/**
 * Testing 2 row 35 regression: when the bundle is stale, a Next.js Server
 * Action throws "Server Action ... was not found on the server". This used
 * to surface as a raw English error in the toast. After the fix, the tab
 * must show the friendly STALE_SERVER_ACTION_MESSAGE and trigger a refresh.
 *
 * Brands tab uses direct Supabase calls today, but the same try/catch
 * handler must still detect this error shape — both for forward-compat
 * (if the API moves behind a Server Action wrapper) and to normalize error
 * handling across all admin-routing tabs.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { STALE_SERVER_ACTION_MESSAGE } from "@/shared/lib/errors";

const deleteBrandAssignmentMock = vi.fn();
const toastErrorMock = vi.fn();
const routerRefreshMock = vi.fn();

vi.mock("../../api/routing-api", () => ({
  createBrandAssignment: vi.fn(),
  updateBrandAssignment: vi.fn(),
  deleteBrandAssignment: (...args: unknown[]) =>
    deleteBrandAssignmentMock(...args),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: (...args: unknown[]) => toastErrorMock(...args),
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: routerRefreshMock }),
}));

// UserSelect pulls a Supabase client at import time — stub it out.
vi.mock("../user-select", () => ({
  UserSelect: () => null,
}));

vi.mock("../brand-assignment-dialog", () => ({
  BrandAssignmentDialog: () => null,
}));

import { BrandsTab } from "../brands-tab";
import type { BrandAssignment } from "../../model/types";

const SAMPLE_ASSIGNMENT: BrandAssignment = {
  id: "assignment-1",
  brand: "ACME",
  user_id: "user-1",
  user_full_name: "Иван Закупщик",
  user_email: "ivan@example.com",
  created_at: "2026-05-01T10:00:00Z",
};

describe("BrandsTab — stale Server Action guard (Testing 2 row 35)", () => {
  beforeEach(() => {
    deleteBrandAssignmentMock.mockReset();
    toastErrorMock.mockReset();
    routerRefreshMock.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows STALE_SERVER_ACTION_MESSAGE when the mutation rejects with the stale-action error", async () => {
    deleteBrandAssignmentMock.mockRejectedValueOnce(
      new Error("Server Action was not found on the server"),
    );

    render(
      <BrandsTab
        assignments={[SAMPLE_ASSIGNMENT]}
        unassignedBrands={[]}
        orgId="org-1"
      />,
    );

    const deleteButton = screen.getByTitle("Удалить");
    await userEvent.click(deleteButton);

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith(STALE_SERVER_ACTION_MESSAGE);
    });
    expect(routerRefreshMock).toHaveBeenCalled();
  });

  it("falls back to the extracted error message for non-stale errors", async () => {
    deleteBrandAssignmentMock.mockRejectedValueOnce(
      new Error("permission denied"),
    );

    render(
      <BrandsTab
        assignments={[SAMPLE_ASSIGNMENT]}
        unassignedBrands={[]}
        orgId="org-1"
      />,
    );

    const deleteButton = screen.getByTitle("Удалить");
    await userEvent.click(deleteButton);

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith("permission denied");
    });
    // Non-stale errors don't trigger a refresh.
    expect(routerRefreshMock).not.toHaveBeenCalled();
  });
});
