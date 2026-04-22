/**
 * URL helpers for the "Report issue" flow invoked from /journey.
 *
 * Spec: .kiro/specs/customer-journey-map/requirements.md Req 11.3 — a
 * /journey drawer's "view all" and "report issue" affordances navigate to
 * /admin/feedback?node_id=<id>. The list-filter path uses the query param;
 * the create-feedback path reuses the same param so that after submission,
 * the reporting user lands on the filtered list already showing their row.
 *
 * Kept as a standalone pure helper so it can be unit-tested without a DOM
 * environment (the workspace vitest config runs without jsdom/happy-dom).
 */

/**
 * Build the URL a /journey drawer's "View all feedback" link should use.
 *
 * @param nodeId  Stable journey node id. Must match the `app:<route>` or
 *                `ghost:<slug>` shape enforced by `JourneyNodeId`.
 * @returns Relative path + encoded query string, e.g.
 *          `/admin/feedback?node_id=app%3A%2Fquotes%2F%5Bid%5D`.
 */
export function feedbackListUrlForNode(nodeId: string): string {
  const params = new URLSearchParams({ node_id: nodeId });
  return `/admin/feedback?${params.toString()}`;
}

/**
 * Build the URL a /journey drawer's "Report issue" CTA should use.
 *
 * There is no dedicated feedback-creation page in the current app — new
 * feedback is produced inline via `FeedbackModal`. We still expose a URL
 * here for two reasons:
 *   1. The spec wording ("opens feedback creation with ?node_id=<id>
 *      prefilled") implies a URL-level contract usable by anywhere in
 *      the app, including deep links from e-mail / ClickUp.
 *   2. Task 18 may later migrate the drawer to a standalone `/admin/feedback
 *      /new` route; keeping the URL-builder centralised insulates callers
 *      from that change.
 *
 * Today the URL degrades to the admin feedback list with the filter applied.
 * The same `node_id` is forwarded to the inline modal via the `nodeId` prop,
 * so the submitted row is tagged correctly regardless of which surface
 * opened the modal.
 */
export function reportIssueUrlForNode(nodeId: string): string {
  return feedbackListUrlForNode(nodeId);
}
