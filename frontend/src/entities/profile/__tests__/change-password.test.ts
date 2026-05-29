import { describe, it, expect, vi, beforeEach } from "vitest";

const signInWithPassword = vi.fn();
const updateUser = vi.fn();

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signInWithPassword, updateUser } }),
}));

import { changePassword } from "@/entities/profile/mutations";

describe("changePassword", () => {
  beforeEach(() => {
    signInWithPassword.mockReset();
    updateUser.mockReset();
  });

  it("re-verifies the current password then updates", async () => {
    signInWithPassword.mockResolvedValue({ error: null });
    updateUser.mockResolvedValue({ error: null });

    await changePassword("u@x.com", "oldpw123", "newpw456");

    expect(signInWithPassword).toHaveBeenCalledWith({
      email: "u@x.com",
      password: "oldpw123",
    });
    expect(updateUser).toHaveBeenCalledWith({ password: "newpw456" });
  });

  it("throws CURRENT_PASSWORD_INVALID and does NOT update when current password is wrong", async () => {
    signInWithPassword.mockResolvedValue({ error: { message: "bad" } });

    await expect(
      changePassword("u@x.com", "wrong", "newpw456")
    ).rejects.toThrow("CURRENT_PASSWORD_INVALID");
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("propagates an updateUser error", async () => {
    signInWithPassword.mockResolvedValue({ error: null });
    updateUser.mockResolvedValue({ error: new Error("weak password") });

    await expect(
      changePassword("u@x.com", "oldpw123", "x")
    ).rejects.toThrow("weak password");
  });
});
