# Research Log — feedback-page-enhancements

## Summary

Light discovery for an extension of the existing `/admin/feedback` list page. No architectural changes — adding TanStack React Table as a new dependency to enable row expansion and row selection, plus inline status mutations and a bulk update API.

## Investigation Topics

### 1. TanStack React Table Compatibility

**Source:** TanStack docs, project package.json  
**Finding:** `@tanstack/react-table` v8 is headless (no DOM output), works with any UI library including shadcn. It provides `getExpandedRowModel()` and `getRowSelectionModel()` as plugins. The project already uses `@tanstack/react-query` so the TanStack ecosystem is familiar.  
**Implication:** No compatibility risk. Headless design means we keep using shadcn Table components for rendering.

### 2. Existing Patterns in Codebase

**Source:** Grep for `useFilterNavigation`, toast, Select patterns  
**Findings:**
- `useFilterNavigation` (shared/lib) handles URL param updates with automatic page reset — reuse for pageSize changes
- Toast notifications use `sonner` (`import { toast } from "sonner"`) — consistent across 50+ files
- `Select` from shadcn/ui with `stopPropagation` pattern exists in garson-client reference
- `Checkbox` component exists at `components/ui/checkbox.tsx`
- Existing `updateFeedbackStatus` mutation in `entities/admin/mutations.ts` uses Supabase client-side

**Implication:** All integration patterns are established. No new patterns needed.

### 3. Bulk Update API

**Source:** Supabase JS docs  
**Finding:** `.update({...}).in('column', array)` is supported for batch updates. Single round-trip, atomic per-row (not transactional across rows, but acceptable for status updates).  
**Implication:** No API endpoint needed — direct Supabase client call from frontend.

### 4. Integration Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| TanStack table re-render overhead with 100 rows | Low | Headless — no extra DOM, column memoization |
| Expanded row content causes layout shift | Medium | Fixed-height container or CSS transition |
| Optimistic update race with bulk update | Low | Disable inline status dropdown for selected rows during bulk |

## Architecture Decisions

- **AD-1:** Use TanStack React Table headless — render via existing shadcn Table components
- **AD-2:** Single expanded row model (not multi-expand) — better for triage scanning
- **AD-3:** Bulk mutations use Supabase `.in()` filter, not a custom API endpoint
- **AD-4:** Page size persisted in URL params via existing `useFilterNavigation` hook
