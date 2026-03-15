# Research & Design Decisions

## Summary
- **Feature**: `phmb-registry`
- **Discovery Scope**: Extension (new page following established FSD patterns)
- **Key Findings**:
  - Customers list page is the exact blueprint for registry pattern (table + search + pagination)
  - Quote creation needs typeahead — customer search pattern already exists in customers entity
  - PHMB status is derived (draft/waiting/ready), not stored — computed from phmb_quote_items counts

## Research Log

### Registry Pattern (customers list as reference)
- **Context**: Need a list page with search, filter, pagination
- **Sources**: `frontend/src/app/(app)/customers/page.tsx`, `entities/customer/queries.ts`
- **Findings**: Customers page uses server component + fetchCustomersList with pagination. Search + status filter via query params. shadcn Table for display. Pattern is directly reusable.
- **Implications**: phmb-quote entity follows same structure: types → queries → mutations → barrel

### PHMB Quote Status Derivation
- **Context**: Status isn't a stored column — must be computed
- **Findings**:
  - `draft` = quote has 0 items in phmb_quote_items
  - `waiting_prices` = has items but some lack price (phmb_quote_items where purchase_price is null)
  - `ready` = all items have prices and are calculated
- **Implications**: Status computed in query via subquery counting priced vs total items. Not a simple column filter.

### Typeahead Customer Search
- **Context**: Create dialog needs customer typeahead
- **Findings**: No existing typeahead component in the Next.js frontend. FastHTML uses HTMX for typeahead. Need to build a simple one with shadcn Command/Combobox + debounced Supabase query.
- **Implications**: New reusable component in shared/ui or features/phmb. Keep simple — Input + dropdown, not full Command palette.

## Design Decisions

### Decision: Compute status in query vs store in DB
- **Selected**: Compute in query via subquery
- **Rationale**: No migration needed. Status always fresh. phmb_quote_items is the source of truth.
- **Trade-off**: Slightly more complex query, but avoids sync issues.

### Decision: Customer typeahead — shared vs feature-local
- **Selected**: Feature-local for now, promote to shared later if reused
- **Rationale**: YAGNI. Only PHMB needs it today. If quotes/new also needs it later, extract then.

## Risks & Mitigations
- Risk: Status subquery may be slow with many quotes → Mitigation: LIMIT + index on phmb_quote_items.quote_id
- Risk: Typeahead floods DB with queries → Mitigation: 300ms debounce + minimum 2 chars
