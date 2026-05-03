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
 *    error. Migration 301 widens the policy.
 *    (РОП Тест 2026-05-03 fail RPQ11–RPQ17.)
 *
 * Order: comment INSERT first, then documents.update. The original "link
 * before insert" approach (МОЗ #39/#42/#43 realtime-race fix) violated
 * documents_comment_id_fkey because that FK is NOT deferrable — the link
 * UPDATE could not reference a comment id that did not yet exist. Receiver-
 * side race for fresh attachments is now handled by useRealtimeComments
 * subscribing to documents UPDATE events.
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
  /** Echoed back as the inserted row id so the mutation can use it. */
  id: string;
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
  /** Captured comment IDs that were deleted (best-effort cleanup path). */
  commentsDeletes: string[];
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
    commentsDeletes: [],
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
            const id = `comment-${state.commentsInserts.length + 1}`;
            state.commentsInserts.push({
              id,
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
                  return { data: { id, ...payload }, error: null };
                },
              }),
            };
          },
          delete: () => ({
            eq: (_col: string, id: string) => {
              state.commentsDeletes.push(id);
              // Match the mutation's chained `.then(undefined, () => {})`
              // best-effort signature.
              return {
                then: (onFulfilled?: (v: unknown) => unknown) => {
                  const v = { error: null };
                  return Promise.resolve(
                    onFulfilled ? onFulfilled(v) : v
                  );
                },
              };
            },
          }),
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

  it("inserts the comment row BEFORE linking documents", async () => {
    // The FK kvota.documents.comment_id → kvota.quote_comments.id is NOT
    // deferrable, so any UPDATE that names a comment id that does not yet
    // exist returns 23503/409 (МОП Тест 2026-05-03 fail M9–M13).
    const { sendQuoteComment } = await import("../mutations");

    await sendQuoteComment("q-1", "user-1", "hello", undefined, ["doc-1"]);

    expect(fakeSupabase.documentsUpdates).toHaveLength(1);
    expect(fakeSupabase.commentsInserts).toHaveLength(1);

    // Comment INSERT precedes documents UPDATE.
    expect(fakeSupabase.commentsInserts[0].order).toBeLessThan(
      fakeSupabase.documentsUpdates[0].order
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

  it("rolls back the comment when the documents link UPDATE fails", async () => {
    // Pre-migration-301 head_of_sales scenario: documents.update is rejected
    // by RLS. The comment was already inserted (Step 1), so we delete it as
    // best-effort cleanup so receivers don't see an empty bubble where a
    // file should be.
    fakeSupabase.failDocumentsUpdate = true;

    const { sendQuoteComment } = await import("../mutations");

    await expect(
      sendQuoteComment("q-1", "user-1", "hello", undefined, ["doc-1"])
    ).rejects.toBeTruthy();

    expect(fakeSupabase.commentsInserts).toHaveLength(1);
    expect(fakeSupabase.documentsUpdates).toHaveLength(1);
    // Cleanup ran (best-effort delete of the orphan comment).
    expect(fakeSupabase.commentsDeletes).toHaveLength(1);
    expect(fakeSupabase.commentsDeletes[0]).toEqual(
      fakeSupabase.commentsInserts[0].id
    );
  });

  it("does not link or touch documents when the comment INSERT fails", async () => {
    // Simulate a constraint / RLS violation on the comments insert. The
    // mutation must throw without touching documents — there's no comment
    // id to link to.
    fakeSupabase.failCommentInsert = true;

    const { sendQuoteComment } = await import("../mutations");

    await expect(
      sendQuoteComment("q-1", "user-1", "hello", undefined, ["doc-1"])
    ).rejects.toBeTruthy();

    expect(fakeSupabase.commentsInserts).toHaveLength(1);
    expect(fakeSupabase.documentsUpdates).toHaveLength(0);
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
