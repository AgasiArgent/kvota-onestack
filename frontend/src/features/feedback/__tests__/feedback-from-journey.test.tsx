/**
 * Journey → feedback plumbing tests.
 *
 * Spec: .kiro/specs/customer-journey-map/requirements.md Req 11.1, 11.3.
 *
 * The workspace vitest config does not provide a DOM (no jsdom/happy-dom),
 * so we unit-test the pure plumbing that powers the drawer:
 *   1. URL builders — the drawer's "View all feedback" / "Report issue"
 *      affordances must produce `/admin/feedback?node_id=<id>` with correct
 *      encoding.
 *   2. Modal submit payload — the `FeedbackModal` forwards the `nodeId`
 *      prop to `submitFeedback`, which in turn forwards it to the
 *      `apiClient` POST body as `node_id`.
 *
 * (Full interactive drawer behaviour — actual click + render — is covered
 * by localhost browser verification during deploy, matching the pattern used
 * by `substatus-reason-dialog.test.ts`.)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  feedbackListUrlForNode,
  reportIssueUrlForNode,
} from "../lib/reportIssueUrl";

// ---------------------------------------------------------------------------
// 1. URL builders
// ---------------------------------------------------------------------------

describe("feedbackListUrlForNode", () => {
  it("builds /admin/feedback with node_id query param", () => {
    expect(feedbackListUrlForNode("app:/quotes")).toBe(
      "/admin/feedback?node_id=app%3A%2Fquotes"
    );
  });

  it("encodes bracketed dynamic segments", () => {
    // Dynamic routes use [id] which contains reserved URL characters.
    expect(feedbackListUrlForNode("app:/quotes/[id]")).toBe(
      "/admin/feedback?node_id=app%3A%2Fquotes%2F%5Bid%5D"
    );
  });

  it("accepts ghost nodes", () => {
    expect(feedbackListUrlForNode("ghost:planned-customs-ui")).toBe(
      "/admin/feedback?node_id=ghost%3Aplanned-customs-ui"
    );
  });

  it("round-trips cleanly through URLSearchParams", () => {
    const nodeId = "app:/procurement/[id]/review";
    const url = feedbackListUrlForNode(nodeId);
    const query = url.split("?")[1];
    const parsed = new URLSearchParams(query);
    expect(parsed.get("node_id")).toBe(nodeId);
  });
});

describe("reportIssueUrlForNode", () => {
  it("currently mirrors the list URL (no dedicated create route exists yet)", () => {
    const nodeId = "app:/quotes/[id]";
    expect(reportIssueUrlForNode(nodeId)).toBe(feedbackListUrlForNode(nodeId));
  });

  it("still carries node_id when the node is a ghost", () => {
    const nodeId = "ghost:customs-expenses-editor";
    expect(reportIssueUrlForNode(nodeId)).toBe(
      "/admin/feedback?node_id=ghost%3Acustoms-expenses-editor"
    );
  });
});

// ---------------------------------------------------------------------------
// 2. Modal submit payload — node_id is forwarded to the API
// ---------------------------------------------------------------------------

/**
 * `submitFeedback` depends on the browser-only Supabase client and the
 * `apiClient` wrapper. We stub both modules so we can assert the request
 * body ships `node_id` exactly when the caller passed it in.
 */
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({
        data: { session: { access_token: "test-token", user: { id: "u1" } } },
      }),
    },
    storage: {
      from: () => ({
        upload: async () => ({ error: null }),
        getPublicUrl: () => ({ data: { publicUrl: "" } }),
      }),
    },
  }),
}));

interface ApiClientCall {
  (path: string, options?: { body?: string }): Promise<{
    success: true;
    data: { short_id: string };
  }>;
}

const apiClientMock = vi.fn<ApiClientCall>(async () => ({
  success: true,
  data: { short_id: "FB-UNIT-1" },
}));

vi.mock("@/shared/lib/api", () => ({
  apiClient: (path: string, options?: { body?: string }) =>
    apiClientMock(path, options),
}));

// Dynamic import so the mocks above are in scope before the module loads.
async function loadSubmitFeedback() {
  const mod = await import("../api/submitFeedback");
  return mod.submitFeedback;
}

describe("submitFeedback — node_id payload", () => {
  beforeEach(() => {
    apiClientMock.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("includes node_id in the POST body when provided (drawer path)", async () => {
    const submitFeedback = await loadSubmitFeedback();
    await submitFeedback({
      feedbackType: "bug",
      description: "button does nothing",
      pageUrl: "https://app.kvotaflow.ru/journey",
      pageTitle: "Journey",
      debugContext: {
        url: "https://app.kvotaflow.ru/journey",
        title: "Journey",
      } as never,
      nodeId: "app:/quotes/[id]",
    });

    expect(apiClientMock).toHaveBeenCalledTimes(1);
    const call = apiClientMock.mock.calls[0];
    const options = call?.[1];
    if (!options?.body) throw new Error("apiClient was called without a body");
    const body = JSON.parse(options.body);
    expect(body.node_id).toBe("app:/quotes/[id]");
  });

  it("omits node_id when the caller has no journey context (legacy path)", async () => {
    const submitFeedback = await loadSubmitFeedback();
    await submitFeedback({
      feedbackType: "bug",
      description: "regression",
      pageUrl: "https://app.kvotaflow.ru/quotes",
      pageTitle: "Quotes",
      debugContext: {
        url: "https://app.kvotaflow.ru/quotes",
        title: "Quotes",
      } as never,
    });

    expect(apiClientMock).toHaveBeenCalledTimes(1);
    const call = apiClientMock.mock.calls[0];
    const options = call?.[1];
    if (!options?.body) throw new Error("apiClient was called without a body");
    const body = JSON.parse(options.body);
    expect(body).not.toHaveProperty("node_id");
  });
});
