/**
 * Scroll preservation helpers.
 *
 * Background: many of our pages trigger a server-revalidation flow on mutate
 * (`router.refresh()` + a parent `onMutation` that increments a tick driving
 * a Supabase reload). The reload briefly toggles a loading state that
 * collapses the layout — at which point browser native scroll restoration
 * falls back to `scrollTop=0` and the user loses their place on long pages.
 *
 * `preserveScroll` snapshots `window.scrollY` BEFORE the mutation runs and
 * restores it AFTER the post-mutation render cycle. The restore is scheduled
 * via a two-rAF chain: the first rAF waits for React to commit the new tree,
 * the second waits for the browser to lay out / paint the new DOM, so the
 * scroll target is reachable by the time we call `scrollTo`.
 *
 * Used by:
 *   - features/route-constructor (Testing 2 row 58)
 *   - features/workspace-kanban (Testing 2 rows 62/63 — post-assignment)
 *
 * Why a helper, not inline copy: 3 callers, identical algorithm. Inline
 * duplication invites drift (e.g. someone forgets the second rAF).
 */

/**
 * Run `action` while preserving the current window scroll position. The
 * snapshot is taken synchronously before the action runs; the restore is
 * fired after the action's promise settles, on a two-rAF chain so the
 * browser has time to flush the post-mutation render and lay out.
 *
 * No-ops on the server (no `window`) and when scrollY is 0 (nothing to
 * restore — saves a redundant `scrollTo` call).
 */
export async function preserveScroll(action: () => Promise<void>): Promise<void> {
  const savedScrollY = typeof window !== "undefined" ? window.scrollY : 0;
  try {
    await action();
  } finally {
    if (typeof window !== "undefined" && savedScrollY > 0) {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          window.scrollTo({ top: savedScrollY, behavior: "instant" });
        });
      });
    }
  }
}
