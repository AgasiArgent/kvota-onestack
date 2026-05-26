// @vitest-environment jsdom
/**
 * Testing 2 row 77 — UI guard for blocked location deletes.
 *
 * Verifies that when `deleteLocation` returns `{ success: false, usage: [...] }`
 * (the "used in N КП" path), the table surfaces a helpful error toast listing
 * each referencing table and its row count — not a generic «не удалось»
 * fallback. Successful deletes still trigger the success toast + router
 * refresh.
 *
 * The button is only rendered when `canDelete` is true, matching the role
 * gate enforced by the server action (admin / head_of_logistics /
 * head_of_customs).
 */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { LocationListItem } from "../../model/types";

// ---------------------------------------------------------------------------
// Mocks — hoisted by vitest before any import statement
// ---------------------------------------------------------------------------

const deleteLocationMock = vi.fn();
const routerRefreshMock = vi.fn();
const toastSuccessMock = vi.fn();
const toastErrorMock = vi.fn();

vi.mock("@/entities/location/server-actions", () => ({
  deleteLocation: (...args: unknown[]) => deleteLocationMock(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: routerRefreshMock,
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccessMock(...args),
    error: (...args: unknown[]) => toastErrorMock(...args),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

// Stub the inline type-cell — its Base UI dropdown pulls in floating-ui
// pieces unrelated to this test's surface.
vi.mock("../location-type-cell", () => ({
  LocationTypeCell: () => null,
}));

import { LocationsTable } from "../locations-table";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const baseLocation: LocationListItem = {
  id: "loc-1",
  country: "Китай",
  city: "Шанхай",
  code: "SH",
  is_active: true,
  location_type: "hub",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LocationsTable — DeleteLocationButton (Testing 2 row 77)", () => {
  let confirmSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    deleteLocationMock.mockReset();
    routerRefreshMock.mockReset();
    toastSuccessMock.mockReset();
    toastErrorMock.mockReset();
    confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    confirmSpy.mockRestore();
    cleanup();
  });

  it("hides the delete button when canDelete=false", () => {
    render(<LocationsTable locations={[baseLocation]} canDelete={false} />);
    expect(
      screen.queryByRole("button", { name: "Удалить локацию" }),
    ).toBeNull();
  });

  it("renders the delete button when canDelete=true", () => {
    render(<LocationsTable locations={[baseLocation]} canDelete />);
    expect(
      screen.getByRole("button", { name: "Удалить локацию" }),
    ).toBeInTheDocument();
  });

  it("does nothing when the user cancels the confirm dialog", async () => {
    confirmSpy.mockReturnValue(false);
    render(<LocationsTable locations={[baseLocation]} canDelete />);

    const btn = screen.getByRole("button", { name: "Удалить локацию" });
    fireEvent.click(btn);

    expect(confirmSpy).toHaveBeenCalledWith(
      'Удалить локацию «SH (Китай, Шанхай)»?',
    );
    expect(deleteLocationMock).not.toHaveBeenCalled();
    expect(toastErrorMock).not.toHaveBeenCalled();
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("shows success toast + refreshes router when delete succeeds", async () => {
    deleteLocationMock.mockResolvedValue({ success: true });
    render(<LocationsTable locations={[baseLocation]} canDelete />);

    fireEvent.click(screen.getByRole("button", { name: "Удалить локацию" }));

    await waitFor(() => {
      expect(deleteLocationMock).toHaveBeenCalledWith("loc-1");
    });
    await waitFor(() => {
      expect(toastSuccessMock).toHaveBeenCalledWith("Локация удалена");
    });
    expect(routerRefreshMock).toHaveBeenCalledTimes(1);
    expect(toastErrorMock).not.toHaveBeenCalled();
  });

  it("shows «используется» error toast with usage list when blocked by FK references", async () => {
    deleteLocationMock.mockResolvedValue({
      success: false,
      error: "Локация используется и не может быть удалена",
      usage: [
        { label: "позиции КП", count: 3 },
        { label: "сегменты маршрутов (откуда)", count: 1 },
      ],
    });
    render(<LocationsTable locations={[baseLocation]} canDelete />);

    fireEvent.click(screen.getByRole("button", { name: "Удалить локацию" }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith(
        "Нельзя удалить — локация используется: позиции КП (3), сегменты маршрутов (откуда) (1)",
      );
    });
    expect(routerRefreshMock).not.toHaveBeenCalled();
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("shows the server's error message when delete fails without usage", async () => {
    deleteLocationMock.mockResolvedValue({
      success: false,
      error: "Локация не найдена",
    });
    render(<LocationsTable locations={[baseLocation]} canDelete />);

    fireEvent.click(screen.getByRole("button", { name: "Удалить локацию" }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith("Локация не найдена");
    });
    expect(routerRefreshMock).not.toHaveBeenCalled();
  });

  it("falls back to «Не удалось удалить локацию» when error message missing", async () => {
    deleteLocationMock.mockResolvedValue({ success: false });
    render(<LocationsTable locations={[baseLocation]} canDelete />);

    fireEvent.click(screen.getByRole("button", { name: "Удалить локацию" }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith(
        "Не удалось удалить локацию",
      );
    });
  });

  it("includes both code and city in the confirm label", () => {
    render(<LocationsTable locations={[baseLocation]} canDelete />);
    fireEvent.click(screen.getByRole("button", { name: "Удалить локацию" }));
    expect(confirmSpy).toHaveBeenCalledWith(
      'Удалить локацию «SH (Китай, Шанхай)»?',
    );
  });

  it("omits empty usage array from the «используется» path (falls back to error)", async () => {
    deleteLocationMock.mockResolvedValue({
      success: false,
      error: "Other error",
      usage: [],
    });
    render(<LocationsTable locations={[baseLocation]} canDelete />);

    fireEvent.click(screen.getByRole("button", { name: "Удалить локацию" }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith("Other error");
    });
  });
});
