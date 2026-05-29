import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { changePassword } = vi.hoisted(() => ({ changePassword: vi.fn() }));
vi.mock("@/entities/profile/mutations", () => ({ changePassword }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

import { ChangePasswordSection } from "@/features/profile/ui/change-password-section";

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe("ChangePasswordSection", () => {
  beforeEach(() => changePassword.mockReset());

  it("rejects a new password shorter than 8 chars", async () => {
    render(<ChangePasswordSection email="u@x.com" />);
    fill("Текущий пароль", "oldpw123");
    fill("Новый пароль", "short");
    fill("Повторите новый пароль", "short");
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    expect(await screen.findByText(/не короче 8/i)).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("rejects mismatched confirmation", async () => {
    render(<ChangePasswordSection email="u@x.com" />);
    fill("Текущий пароль", "oldpw123");
    fill("Новый пароль", "newpw456");
    fill("Повторите новый пароль", "different");
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    expect(await screen.findByText(/не совпадают/i)).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("calls changePassword on a valid submit", async () => {
    changePassword.mockResolvedValue(undefined);
    render(<ChangePasswordSection email="u@x.com" />);
    fill("Текущий пароль", "oldpw123");
    fill("Новый пароль", "newpw456");
    fill("Повторите новый пароль", "newpw456");
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    await waitFor(() =>
      expect(changePassword).toHaveBeenCalledWith("u@x.com", "oldpw123", "newpw456")
    );
  });

  it("shows a field error when the current password is wrong", async () => {
    changePassword.mockRejectedValueOnce(new Error("CURRENT_PASSWORD_INVALID"));
    render(<ChangePasswordSection email="u@x.com" />);
    fill("Текущий пароль", "wrongpw1");
    fill("Новый пароль", "newpw456");
    fill("Повторите новый пароль", "newpw456");
    fireEvent.click(screen.getByRole("button", { name: "Сменить пароль" }));
    await waitFor(() =>
      expect(screen.getByText(/неверный текущий пароль/i)).toBeInTheDocument()
    );
  });
});
