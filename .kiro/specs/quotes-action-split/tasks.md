# Implementation Plan

- [ ] 1. Role-to-status action mapping
- [ ] 1.1 Create action status config and helper
  - Define ROLE_ACTION_STATUSES constant mapping each role to its "requires action" workflow statuses
  - Create getActionStatusesForUser(roles: string[]) that returns the union of all action statuses for the user's roles
  - Place in entities/quote alongside STATUS_GROUPS config
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 2. Split quotes in the server component
- [ ] 2.1 Partition fetch results into action vs other
  - In the quotes page server component, after fetching quotes, split into two arrays using getActionStatusesForUser()
  - Pass both arrays (actionQuotes, otherQuotes) plus action count to the client component
  - _Requirements: 1.1, 1.4, 3.1, 3.2_

- [ ] 3. Update QuotesTable for split rendering
- [ ] 3.1 Render two sections with visual separation
  - Add "Требует вашего действия (N)" header with accent styling when actionQuotes is non-empty
  - Render action quotes table rows
  - Add visual divider
  - Add muted "Остальные КП" header
  - Render remaining quotes table rows
  - Both sections share the same table headers/columns
  - _Requirements: 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.3_
