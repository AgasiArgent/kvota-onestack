import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Regression tests for sendQuoteComment + chat attachment linking.
 *
 * Two distinct bugs exercised:
 *
 * 1. /messages chat: the inbox's `ActiveChat` previously wrapped
 *    useRealtimeComments.sendMessage in a 2-arg shim that dropped the
 *    third argument (attachmentDocumentIds). Files were uploaded but
 *    never linked to the comment row, so the bubble rendered with no
 *    file and the user saw the file disappear from the upload area.
 *    (МОП Тест 2026-05-03 fail M9–M13.)
 *
 * 2. РОП on quote chat: head_of_sales (and other heads / top_manager)
 *    were missing from kvota.documents RLS allowlist (migration 143),
 *    so the documents.update({comment_id}) step rejected with a 42501
 *    error. Migration 301 widens the policy. The mutation contract is
 *    "if the link UPDATE fails, throw — do NOT insert the comment", so
 *    we verify the order and the rollback.
 *    (РОП Тест 2026-05-03 fail RPQ11–RPQ17.)
 *
 * The fakeSupabase here mimics the chained PostgREST builder for the
 * three tables sendQuoteComment touches: documents (update + select)
 * and quote_comments (insert + select).
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

interface DocumentRow {
  id: string;
  original_filename: string;
  storage_path: string;
  mime_type: string | null;
  file_size_bytes: number | null;
  comment_id: string | null;
}

interface DocumentsUpdateCall {
  updates: Record<string, unknown>;
  ids: string[];
  /** Order in which this call happened relative to the comment insert. */
  order: number;
}

interface CommentsInsertCall {
  payload: Record<string, unknown>;
  /** Order in which this call happened relative to documents updates. */
  order: number;
}

interface FakeSupabase {
  // Test fixtures
  documents: DocumentRow[];
  /** When true, documents.update() returns an RLS-style error. */
  failDocumentsUpdate: boolean;
  /** When true, quote_comments.insert() returns an error. */
  failCommentInsert: boolean;

  // Captured operations (in call order)
  documentsUpdates: DocumentsUpdateCall[];
  commentsInserts: CommentsInsertCall[];
  /** Monotonic counter so we can assert ordering. */
  callCounter: number;

  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(initialDocs: DocumentRow[] = []): FakeSupabase {
  const state: FakeSupabase = {
    documents: [...initialDocs],
    failDocumentsUpdate: false,
    failCommentInsert: false,
    documentsUpdates: [],
    commentsInserts: [],
    callCounter: 0,
    from(table: string) {
      if (table === "documents") {
        return {
          update: (updates: Record<string, unknown>) => ({
            in: async (_col: string, ids: string[]) => {
              state.documentsUpdates.push({
                updates,
                ids,
                order: ++state.callCounter,
              });
              if (state.failDocumentsUpdate) {
                return {
                  error: {
                    code: "42501",
                    message: "new row violates row-level security policy",
                  },
                };
              }
              // Apply update to in-memory state so a subsequent select
              // reflects the linked rows.
              for (const doc of state.documents) {
                if (ids.includes(doc.id)) {
                  Object.assign(doc, updates);
                }
              }
              // The mutation chains a `.then(undefined, () => {})` for the
              // rollback path; vanilla Promise resolution covers both.
              return { error: null };
            },
          }),
          select: (_cols: string) => ({
            in: async (_col: string, ids: string[]) => {
              const data = state.documents.filter((d) => ids.includes(d.id));
              return { data, error: null };
            },
          }),
        };
      }
      if (table === "quote_comments") {
        return {
          insert: (payload: Record<string, unknown>) => {
            state.commentsInserts.push({
              payload,
              order: ++state.callCounter,
            });
            return {
              select: () => ({
                single: async () => {
                  if (state.failCommentInsert) {
                    return {
                      data: null,
                      error: { message: "insert blocked" },
                    };
                  }
                  return { data: payload, error: null };
                },
              }),
            };
          },
        };
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

describe("sendQuoteComment — attachment link ordering", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase([
      {
        id: "doc-1",
        original_filename: "spec.pdf",
        storage_path: "quotes/q-1/spec.pdf",
        mime_type: "application/pdf",
        file_size_bytes: 1024,
        comment_id: null,
      },
    ]);
  });

  it("links documents BEFORE inserting the comment row", async () => {
    const { sendQuoteComment } = await import("../mutations");

    await sendQuoteComment("q-1", "user-1", "hello", undefined, ["doc-1"]);

    // Both calls happened
    expect(fakeSupabase.documentsUpdates).toHaveLength(1);
    expect(fakeSupabase.commentsInserts).toHaveLength(1);

    // Documents update precedes the comment insert (PR #80 fix — eliminates
    // the realtime race where receivers saw the comment before the link).
    expect(fakeSupabase.documentsUpdates[0].order).toBeLessThan(
      fakeSupabase.commentsInserts[0].order
    );

    // The link payload sets comment_id to the same UUID as the inserted comment
    const linkedCommentId =
      fakeSupabase.documentsUpdates[0].updates.comment_id;
    expect(linkedCommentId).toEqual(
      fakeSupabase.commentsInserts[0].payload.id
    );
  });

  it("returns the linked attachments inline (so optimistic reconcile renders the file)", async () => {
    const { sendQuoteComment } = await import("../mutations");

    const result = await sendQuoteComment(
      "q-1",
      "user-1",
      "hello",
      undefined,
      ["doc-1"]
    );

    expect(result.attachments).toHaveLength(1);
    expect(result.attachments[0]).toMatchObject({
      id: "doc-1",
      original_filename: "spec.pdf",
      storage_path: "quotes/q-1/spec.pdf",
    });
  });

  it("returns empty attachments array when no documents are passed", async () => {
    const { sendQuoteComment } = await import("../mutations");

    const result = await sendQuoteComment("q-1", "user-1", "hello");

    expect(result.attachments).toEqual([]);
    expect(fakeSupabase.documentsUpdates).toHaveLength(0);
  });
});

describe("sendQuoteComment — RLS / failure paths", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase([
      {
        id: "doc-1",
        original_filename: "spec.pdf",
        storage_path: "quotes/q-1/spec.pdf",
        mime_type: "application/pdf",
        file_size_bytes: 1024,
        comment_id: null,
      },
    ]);
  });

  it("aborts WITHOUT inserting a comment when the documents link UPDATE fails", async () => {
    // Simulate the pre-migration-301 head_of_sales scenario: documents.update
    // is rejected by RLS. Mutation must throw and never insert the comment,
    // otherwise we'd ship a broken bubble (comment but no files).
    fakeSupabase.failDocumentsUpdate = true;

    const { sendQuoteComment } = await import("../mutations");

    await expect(
      sendQuoteComment("q-1", "user-1", "hello", undefined, ["doc-1"])
    ).rejects.toBeTruthy();

    expect(fakeSupabase.documentsUpdates).toHaveLength(1);
    // CRITICAL: zero comment inserts on failure (otherwise RPQ11-17 would
    // ship a comment with NULL comment_id docs — no files in the bubble).
    expect(fakeSupabase.commentsInserts).toHaveLength(0);
  });

  it("rolls back the documents link when the comment INSERT fails", async () => {
    // Simulate a constraint / RLS violation on the comments insert. The
    // mutation must NULL out comment_id to avoid orphan documents pointing
    // at a never-created comment.
    fakeSupabase.failCommentInsert = true;

    const { sendQuoteComment } = await import("../mutations");

    await expect(
      sendQuoteComment("q-1", "user-1", "hello", undefined, ["doc-1"])
    ).rejects.toBeTruthy();

    // Two updates: 1) link (success), 2) rollback (set NULL)
    expect(fakeSupabase.documentsUpdates).toHaveLength(2);
    expect(fakeSupabase.documentsUpdates[1].updates).toEqual({
      comment_id: null,
    });
    expect(fakeSupabase.documentsUpdates[1].ids).toEqual(["doc-1"]);
  });
});

describe("sendQuoteComment — attachment-only message (M9 reproduction)", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase([
      {
        id: "doc-1",
        original_filename: "image.png",
        storage_path: "quotes/q-1/image.png",
        mime_type: "image/png",
        file_size_bytes: 2048,
        comment_id: null,
      },
    ]);
  });

  it("accepts an empty body when at least one attachment is present", async () => {
    // M9: paperclip + send without text. Migration 259 already dropped the
    // body-length>0 constraint at the DB layer; this verifies the mutation
    // doesn't add its own client-side gate.
    const { sendQuoteComment } = await import("../mutations");

    const result = await sendQuoteComment("q-1", "user-1", "", undefined, [
      "doc-1",
    ]);

    expect(fakeSupabase.commentsInserts).toHaveLength(1);
    expect(fakeSupabase.commentsInserts[0].payload.body).toBe("");
    expect(result.attachments).toHaveLength(1);
  });
});
