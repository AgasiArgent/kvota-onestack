import { describe, it, expect } from "vitest";

import { isAllowedFile } from "../use-chat-attachments";

/**
 * Regression test for Testing 2 row 32.
 *
 * The chat / Сообщения file upload used to reject macro-enabled Excel
 * (.xlsm — mime `application/vnd.ms-excel.sheet.macroenabled.12`) and
 * other valid files via a mime-type allowlist (added in PR #171). The
 * expected behavior per the test sheet is "поддерживается любой тип
 * файлов" — any file type is accepted.
 *
 * The fix removed the type allowlist entirely; only the 50 MB size cap
 * remains. These tests assert that any file type passes validation and
 * that the size cap is still enforced.
 */

const MB = 1024 * 1024;

function makeFile(name: string, type: string, sizeBytes: number): File {
  const file = new File(["x"], name, { type });
  // File.size is read-only; override for the size-cap assertions.
  Object.defineProperty(file, "size", { value: sizeBytes });
  return file;
}

describe("isAllowedFile — chat attachment validation", () => {
  it("accepts a macro-enabled Excel file (.xlsm)", () => {
    const file = makeFile(
      "Форма_расчета.xlsm",
      "application/vnd.ms-excel.sheet.macroenabled.12",
      2 * MB,
    );
    expect(isAllowedFile(file)).toBe(true);
  });

  it.each([
    ["Форма.xlsm", "application/vnd.ms-excel.sheet.macroenabled.12"],
    ["Документ.docm", "application/vnd.ms-word.document.macroenabled.12"],
    ["Презентация.pptm", "application/vnd.ms-powerpoint.presentation.macroenabled.12"],
    ["Книга.xlsb", "application/vnd.ms-excel.sheet.binary.macroenabled.12"],
    ["архив.rar", "application/vnd.rar"],
    ["заметки.txt", "text/plain"],
    ["data.csv", "text/csv"],
    ["unknown-type", ""],
    ["script.exe", "application/x-msdownload"],
  ])("accepts %s regardless of mime type (%s)", (name, type) => {
    expect(isAllowedFile(makeFile(name, type, 1 * MB))).toBe(true);
  });

  it("accepts a file exactly at the 50 MB size cap", () => {
    expect(isAllowedFile(makeFile("big.xlsm", "", 50 * MB))).toBe(true);
  });

  it("rejects a file above the 50 MB size cap", () => {
    expect(isAllowedFile(makeFile("huge.xlsm", "", 50 * MB + 1))).toBe(false);
  });
});
