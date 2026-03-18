# Research & Design Decisions

## Summary
- **Feature**: quotes-registry-migration
- **Discovery Scope**: Extension (new page in existing Next.js frontend)
- **Key Findings**:
  - Frontend uses SSR-first pattern (server components fetch data, no TanStack Query for lists)
  - Filters sync with URL via form method="GET" — no client-side state library needed
  - CreateQuoteDialog already exists with `{orgId, userId, open, onOpenChange}` interface
  - Role checking via `getSessionUser()` returning `{roles: string[]}` + `hasRole()` helper

## Research Log

### Existing Page Pattern (Customers)
- **Context**: Need to replicate proven patterns for the quotes registry
- **Sources**: `frontend/src/app/(app)/customers/page.tsx`, `features/customers/ui/customers-table.tsx`
- **Findings**:
  - Server component fetches initial data with filters from searchParams
  - Passes data to client table component as props
  - Filters use `<form method="GET">` — browser submits as URL params
  - Pagination builds full URLs: `/page?param=value`
  - shadcn `<Table>` for layout, no DataTable abstraction
- **Implications**: Quotes page follows same pattern. No new libraries needed.

### Status Grouping Approach
- **Context**: 14 workflow_status values need grouping into 5 categories
- **Findings**:
  - Groups: Draft (1), In Progress (3), Approval (4), Deal (3), Closed (2)
  - Filter UI: pill/chip buttons for groups, expandable to individual statuses
  - Supabase filter: `.in('workflow_status', [...statusesInGroup])`
- **Implications**: Grouping is purely frontend — no DB changes needed

### Role-Based Visibility Query
- **Context**: Sales users see only their quotes + assigned customer quotes
- **Findings**:
  - Current FastHTML uses join: `customers.manager_id = user.id`
  - Supabase JS: `.or('created_by.eq.{userId},customer_id.in.({customerIds})')` where customerIds = customers with manager_id = userId
  - Two-step query: 1) fetch customer IDs where manager_id = user, 2) filter quotes
  - Alternative: single query with FK filter — `.or('created_by.eq.{userId},customers!customer_id.manager_id.eq.{userId}')`
- **Implications**: Single query with FK filter is cleaner, avoids extra round-trip

## Design Decisions

### Decision: Server-Side Filtering (SSR)
- **Alternatives**: 1) Client-side with TanStack Query, 2) Server-side with form GET
- **Selected**: Server-side with form GET
- **Rationale**: Matches existing customers/suppliers pattern. Simpler. URL state comes free.
- **Trade-offs**: Full page reload on filter change vs. smoother UX. Acceptable for registry.

### Decision: Status Group UI as Pill Buttons
- **Alternatives**: 1) Dropdown with optgroups, 2) Pill/chip toggle buttons, 3) Tabs
- **Selected**: Pill toggle buttons for groups, dropdown for individual status within group
- **Rationale**: Pills give quick visual scan. Dropdown overlay for power users who need granular filter.
- **Trade-offs**: Takes more horizontal space than a single dropdown. Acceptable — only 5 groups.

## Risks & Mitigations
- Risk: FK filter `.customers!customer_id.manager_id.eq.{userId}` may not work with Supabase JS — Mitigation: fall back to two-step query
- Risk: 14 status values may grow — Mitigation: group config is a constant, easy to extend
