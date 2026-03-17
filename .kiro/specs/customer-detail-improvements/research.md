# Research & Design Decisions

## Summary
- **Feature**: `customer-detail-improvements`
- **Discovery Scope**: Extension (enhancing existing Next.js customer pages)
- **Key Findings**:
  - All existing patterns (inline edit, modal form, mutation, query) are consistent and reusable — no new patterns needed
  - No dedicated user/manager selector component exists — need to create one for call assignment
  - Tables use hardcoded JSX columns (shadcn Table), responsive scroll needs wrapper div only

## Research Log

### Existing Component Patterns
- **Context**: Need to understand how to extend existing UI without breaking patterns
- **Findings**:
  - Inline editing: useState(editing, value, saving) pattern in NotesSection — reuse for general_email
  - Modal forms: Dialog + useState(form, saving, error) + updateField helper — reuse for contracts
  - Mutations: async functions that throw on error, component catches — consistent across all
  - Queries: server-side createClient() + .select() with explicit FK joins — consistent
- **Implications**: All new components follow exact same patterns. No architectural changes.

### User Profile Selection
- **Context**: Call assignment (REQ 4) needs a user dropdown, none exists
- **Findings**:
  - CallFormModal uses contacts array for contact select (not users)
  - Manager display fetches from user_profiles separately
  - Need: fetchOrgUsers() query + UserSelect shared component (or inline Select)
- **Implications**: Create fetchOrgUsers query in entities/customer/queries.ts, use shadcn Select

### Phones JSONB Schema
- **Context**: REQ 3 needs multi-phone support
- **Findings**:
  - Current: single `phone VARCHAR(50)` column
  - Target: `phones JSONB DEFAULT '[]'` with entries `{number, ext, label}`
  - Labels: основной, рабочий, мобильный, добавочный (4 options)
  - Migration: copy existing phone → phones[0] with label "основной"
- **Implications**: Contact form needs dynamic list UI (add/remove entries), display needs primary + tooltip

## Design Decisions

### Decision: Phones as JSONB array vs. separate table
- **Context**: Contacts need multiple phone numbers
- **Alternatives**:
  1. `contact_phones` table with FK to contacts — normalized, complex queries
  2. `phones JSONB[]` column on contacts — denormalized, simple queries
- **Selected**: JSONB column
- **Rationale**: 2-3 phones per contact max, no need for separate queries on phones. Single read/write.
- **Trade-offs**: Can't query by phone number efficiently (acceptable — no such use case)

### Decision: Notes placement — Overview tab only
- **Context**: Notes currently on CRM tab, user wants on Overview
- **Selected**: Move to Overview, remove from CRM entirely (not duplicate)
- **Rationale**: User explicitly requested "move to Overview", duplicating creates sync confusion
- **Trade-offs**: CRM tab loses notes, but Overview is the first tab users see

### Decision: Contracts in Documents tab vs. separate tab
- **Context**: Where to show customer contracts
- **Selected**: Section within Documents tab (alongside КП and Спецификации)
- **Rationale**: Documents tab already handles related document types. Contracts are few per customer (2-3 max). No need for separate tab.
- **Trade-offs**: Documents tab gets busier, mitigated by section headers

## Risks & Mitigations
- **Phone data migration**: Existing phone data must be preserved → migration populates phones[0] from phone column, keeps old column during transition
- **Type regeneration**: After DB migrations, types must be regenerated or build fails → documented in task dependencies
- **Responsive scroll**: Horizontal scroll may hide columns → scrollbar is always visible (not auto-hide)
