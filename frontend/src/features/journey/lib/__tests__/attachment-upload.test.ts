/**
 * Tests for the attachment-upload module (Task 24 — Req 9.6, 9.8).
 *
 * Pure logic only — no browser APIs, no real Supabase. The driver
 * `uploadAttachments` takes function callbacks for upload + cleanup so we
 * can drive the whole thing with plain mocks.
 *
 * Rules under test (Req 9.8):
 *   - max 3 attachments per verification
 *   - max 2 MB per file
 *   - MIME whitelist: image/png, image/jpeg, image/webp
 *
 * Atomic semantics (Req 9.6):
 *   - partial attachment is not permitted — a single failure rolls back all
 *     already-uploaded paths (best-effort cleanup).
 */

import { describe, it, expect, vi } from "vitest";

import {
  MAX_ATTACHMENTS,
  MAX_FILE_BYTES,
  validateAttachments,
  uploadAttachments,
} from "../attachment-upload";

// ---------------------------------------------------------------------------
// File factory — a real File is overkill (vitest node env has it, but we keep
// the shape minimal so tests stay deterministic).
// ---------------------------------------------------------------------------

function makeFile(
  name: string,
  size: number,
  type: string,
): File {
  const blob = new Blob([new Uint8Array(size)], { type });
  return new File([blob], name, { type });
}

// ---------------------------------------------------------------------------
// validateAttachments
// ---------------------------------------------------------------------------

describe("validateAttachments", () => {
  it("accepts three valid images when none exist", () => {
    const files = [
      makeFile("a.png", 100, "image/png"),
      makeFile("b.jpg", 200, "image/jpeg"),
      makeFile("c.webp", 300, "image/webp"),
    ];
    const out = validateAttachments(files, 0);
    expect(out.valid).toHaveLength(3);
    expect(out.rejected).toHaveLength(0);
  });

  it("rejects the 4th file as 'over_limit'", () => {
    const files = [
      makeFile("a.png", 100, "image/png"),
      makeFile("b.png", 100, "image/png"),
      makeFile("c.png", 100, "image/png"),
      makeFile("d.png", 100, "image/png"),
    ];
    const out = validateAttachments(files, 0);
    expect(out.valid).toHaveLength(MAX_ATTACHMENTS);
    expect(out.rejected).toHaveLength(1);
    expect(out.rejected[0].reason).toBe("over_limit");
    expect(out.rejected[0].file.name).toBe("d.png");
  });

  it("rejects when existingCount already fills the bucket", () => {
    const files = [makeFile("a.png", 100, "image/png")];
    const out = validateAttachments(files, MAX_ATTACHMENTS);
    expect(out.valid).toHaveLength(0);
    expect(out.rejected).toHaveLength(1);
    expect(out.rejected[0].reason).toBe("over_limit");
  });

  it("rejects a non-image MIME as 'bad_mime'", () => {
    const files = [
      makeFile("evil.pdf", 100, "application/pdf"),
      makeFile("good.png", 100, "image/png"),
    ];
    const out = validateAttachments(files, 0);
    expect(out.valid).toHaveLength(1);
    expect(out.valid[0].name).toBe("good.png");
    expect(out.rejected).toHaveLength(1);
    expect(out.rejected[0].reason).toBe("bad_mime");
  });

  it("rejects an oversized file as 'too_large'", () => {
    const files = [
      makeFile("big.png", MAX_FILE_BYTES + 1, "image/png"),
      makeFile("ok.png", MAX_FILE_BYTES, "image/png"),
    ];
    const out = validateAttachments(files, 0);
    expect(out.valid).toHaveLength(1);
    expect(out.valid[0].name).toBe("ok.png");
    expect(out.rejected).toHaveLength(1);
    expect(out.rejected[0].reason).toBe("too_large");
  });

  it("processes rejections in order: bad_mime, too_large, over_limit", () => {
    // Crafted so the 4th slot gets an over_limit but earlier ones are bad.
    const files = [
      makeFile("1.pdf", 100, "application/pdf"), // bad_mime
      makeFile("2.png", MAX_FILE_BYTES + 1, "image/png"), // too_large
      makeFile("3.png", 100, "image/png"), // valid
      makeFile("4.png", 100, "image/png"), // valid
      makeFile("5.png", 100, "image/png"), // over_limit (only 2 valid remain)
    ];
    const out = validateAttachments(files, 1); // 1 existing → 2 more allowed
    expect(out.valid).toHaveLength(2);
    const reasons = out.rejected.map((r) => r.reason);
    expect(reasons).toContain("bad_mime");
    expect(reasons).toContain("too_large");
    expect(reasons).toContain("over_limit");
  });
});

// ---------------------------------------------------------------------------
// uploadAttachments
// ---------------------------------------------------------------------------

describe("uploadAttachments", () => {
  it("uploads three files successfully and returns their paths", async () => {
    const files = [
      makeFile("one.png", 100, "image/png"),
      makeFile("two.jpg", 200, "image/jpeg"),
      makeFile("three.webp", 300, "image/webp"),
    ];
    const upload = vi.fn(async (path: string, _file: File) => ({
      data: { path },
      error: null,
    }));
    const remove = vi.fn(async () => ({}));

    const out = await uploadAttachments(files, {
      bucket: "journey-verification-attachments",
      keyPrefix: "app_quotes_new/pin-1",
      supabaseUpload: upload,
      supabaseRemove: remove,
    });

    expect(out.success).toBe(true);
    if (!out.success) return;
    expect(out.paths).toHaveLength(3);
    // Each key must include the prefix and the safe filename.
    for (const p of out.paths) {
      expect(p.startsWith("app_quotes_new/pin-1/")).toBe(true);
    }
    // Safe filename: `one.png` stays alphanumeric; verify no spaces/slashes.
    for (const p of out.paths) {
      expect(/[^A-Za-z0-9._/-]/.test(p)).toBe(false);
    }
    expect(remove).not.toHaveBeenCalled();
    expect(upload).toHaveBeenCalledTimes(3);
  });

  it("rolls back already-uploaded paths on a mid-batch failure", async () => {
    const files = [
      makeFile("a.png", 100, "image/png"),
      makeFile("b.png", 100, "image/png"),
      makeFile("c.png", 100, "image/png"),
    ];
    let call = 0;
    const upload = vi.fn(async (path: string, _file: File) => {
      call += 1;
      if (call === 3) {
        return { data: null, error: { message: "storage full" } };
      }
      return { data: { path }, error: null };
    });
    const remove = vi.fn(async (_paths: string[]) => ({}));

    const out = await uploadAttachments(files, {
      bucket: "journey-verification-attachments",
      keyPrefix: "app_quotes_new/pin-1",
      supabaseUpload: upload,
      supabaseRemove: remove,
    });

    expect(out.success).toBe(false);
    if (out.success) return;
    // First two succeeded → must be cleaned up.
    expect(remove).toHaveBeenCalledTimes(1);
    const removedPaths = remove.mock.calls[0][0] as string[];
    expect(removedPaths).toHaveLength(2);
    expect(out.partialPathsToCleanup).toHaveLength(2);
    expect(out.reason).toContain("storage full");
  });

  it("does not call remove when the very first upload fails", async () => {
    const files = [makeFile("a.png", 100, "image/png")];
    const upload = vi.fn(async () => ({
      data: null,
      error: { message: "boom" },
    }));
    const remove = vi.fn(async () => ({}));

    const out = await uploadAttachments(files, {
      bucket: "journey-verification-attachments",
      keyPrefix: "app_quotes_new/pin-1",
      supabaseUpload: upload,
      supabaseRemove: remove,
    });

    expect(out.success).toBe(false);
    expect(remove).not.toHaveBeenCalled();
  });

  it("sanitises filenames with spaces and unicode", async () => {
    const files = [makeFile("ПривеT мир.png", 100, "image/png")];
    const upload = vi.fn(async (path: string, _file: File) => ({
      data: { path },
      error: null,
    }));
    const remove = vi.fn(async () => ({}));

    const out = await uploadAttachments(files, {
      bucket: "journey-verification-attachments",
      keyPrefix: "app_quotes/pin-1",
      supabaseUpload: upload,
      supabaseRemove: remove,
    });
    expect(out.success).toBe(true);
    if (!out.success) return;
    // Each path: `{prefix}/{uuid}-{safe}` — safe filename preserves extension.
    expect(out.paths[0]).toMatch(/^app_quotes\/pin-1\/[0-9a-f-]+-[A-Za-z0-9._-]+\.png$/);
    expect(out.paths[0]).not.toContain(" ");
  });

  it("returns success with empty paths for an empty file list", async () => {
    const upload = vi.fn();
    const remove = vi.fn();
    const out = await uploadAttachments([], {
      bucket: "journey-verification-attachments",
      keyPrefix: "x/y",
      supabaseUpload: upload,
      supabaseRemove: remove,
    });
    expect(out.success).toBe(true);
    if (!out.success) return;
    expect(out.paths).toHaveLength(0);
    expect(upload).not.toHaveBeenCalled();
  });
});
