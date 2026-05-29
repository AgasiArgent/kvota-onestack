import { describe, it, expect } from "vitest";
import { generatePassword, PASSWORD_CHARSET } from "@/shared/lib/password";

describe("generatePassword", () => {
  it("returns a 12-character string", () => {
    expect(generatePassword()).toHaveLength(12);
  });

  it("uses only characters from the allowed charset", () => {
    for (let i = 0; i < 50; i++) {
      for (const ch of generatePassword()) {
        expect(PASSWORD_CHARSET).toContain(ch);
      }
    }
  });

  it("produces different values across calls", () => {
    const a = generatePassword();
    const b = generatePassword();
    expect(a).not.toEqual(b);
  });
});
