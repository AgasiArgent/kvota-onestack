# Implementation Plan

- [ ] 1. Database schema extensions
- [ ] 1.1 Create migration to add general_email column to customers table
  - Add nullable VARCHAR(255) column for storing customer-wide email address
  - _Requirements: 10.1_

- [ ] 1.2 Create migration to add phones JSONB column to customer_contacts and migrate existing data
  - Add phones column with JSONB type defaulting to empty array
  - Populate phones[0] from existing phone column for all contacts that have a phone value, using label "основной"
  - Keep existing phone column intact during transition
  - _Requirements: 10.2, 10.4_

- [ ] 1.3 Create migration to add assigned_to column to customer_calls
  - Add nullable UUID column referencing auth.users for call assignment
  - _Requirements: 10.3_

- [ ] 1.4 Apply migrations and regenerate frontend TypeScript types
  - Run all three migrations on the database via SSH
  - Regenerate database types to reflect new columns
  - Verify build passes with updated types
  - _Requirements: 10.5_

- [ ] 2. Entity layer updates and responsive table wrapper
- [ ] 2.1 Update customer entity types to include new fields
  - Add general_email to Customer type
  - Add phones array to CustomerContact type alongside existing phone field
  - Add assigned_to and assigned_user_name to CustomerCall type
  - Add CustomerContract type with contract_number, date, status, notes
  - Add PhoneEntry type with number, ext, and label fields
  - _Requirements: 10.1, 10.2, 10.3_

- [ ] 2.2 Add new queries for contracts and organization users
  - Add query to fetch customer contracts ordered by date descending
  - Add query to fetch organization users for assignment dropdown (user_id, full_name)
  - Update calls query to resolve assigned_to into display name via user_profiles join
  - Update calls query to include contact phone and email from customer_contacts
  - _Requirements: 4.3, 5.1, 9.1_

- [ ] 2.3 Add new mutations for general_email and contract CRUD
  - Add mutation to update customer general_email field
  - Add mutations to create, update, and delete customer contracts
  - Follow existing mutation pattern: async function, throw on error
  - _Requirements: 1.3, 9.3, 9.4, 9.5_

- [ ] 2.4 (P) Create responsive table wrapper component
  - Create a shared wrapper that enables horizontal scrolling when table content overflows viewport
  - Ensure scrollbar is always visible (not auto-hidden) when content exceeds container width
  - _Requirements: 8.1, 8.2_

- [ ] 3. Overview tab improvements
- [ ] 3.1 (P) Move notes section from CRM tab to Overview tab
  - Add inline-editable notes section to Overview tab using existing notes component and mutation
  - Display placeholder text when notes are empty
  - Remove notes section from CRM tab
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 3.2 (P) Add general_email field to the requisites card on Overview tab
  - Display general_email in the Реквизиты card with inline editing capability
  - Show muted placeholder when email is empty
  - Save changes using the new general_email mutation
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 4. CRM tab improvements
- [ ] 4.1 (P) Update contact form to support multiple phone numbers
  - Replace single phone input with a dynamic list of phone entries
  - Each entry has number (required), extension (optional), and label dropdown (основной, рабочий, мобильный, добавочный)
  - Allow adding and removing phone entries
  - Initialize with one empty entry for new contacts; populate from phones array for existing contacts
  - Save phones array to the contacts table via existing contact mutation
  - _Requirements: 3.1, 3.2, 3.3_

- [ ] 4.2 (P) Update contacts table to display phones from the array
  - Show primary phone (first array entry) in the contacts table column
  - Show tooltip or expandable view with additional phones when multiple exist
  - _Requirements: 3.5_

- [ ] 4.3 (P) Add call assignment field and display assigned user in calls
  - Add user select dropdown to call creation form, populated from organization users query
  - Default the selected user to the currently logged-in user
  - Display assigned user name in the calls table alongside the creator
  - Visually distinguish when assignee differs from creator (e.g., arrow notation)
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 4.4 (P) Show contact phone and email in the calls list
  - Add contact phone column to the calls table showing primary phone number
  - Show contact email and additional phones on hover or row expansion
  - Display dash when contact has no phone or email
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 4.5 (P) Make customer addresses editable in the CRM tab
  - Add edit button to each address card (legal, actual, postal)
  - Switch to editable text input when edit is activated
  - Save changes using the existing address update mutation
  - Add interface to add and remove warehouse addresses from the JSON array
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 5. Documents tab — contracts section
- [ ] 5.1 (P) Add contracts section to the Documents tab with display and status badges
  - Fetch and display customer contracts as a table section above existing КП and Спецификации sub-tabs
  - Show contract number, date, status with color-coded badges (active=green, suspended=yellow, terminated=red), and notes
  - Include add button to open contract creation form
  - _Requirements: 9.1, 9.2, 9.6_

- [ ] 5.2 (P) Create contract form modal with CRUD operations
  - Build modal form following existing contact form pattern: contract number (required), date, status dropdown, notes
  - Support both create and edit modes (pre-fill for editing)
  - Add delete action with confirmation dialog
  - _Requirements: 9.3, 9.4, 9.5_

- [ ] 6. Positions tab — SKU column split
- [ ] 6.1 (P) Split the combined SKU column into separate article and IDN-SKU columns
  - Display sku as "Артикул" column and idn_sku as "IDN-SKU" column in the positions table
  - Ensure both columns are visible and not aliased together
  - _Requirements: 7.1, 7.2_

- [ ] 7. Apply responsive table wrapper to all customer tabs
- [ ] 7.1 Wrap all data tables across customer tabs with the responsive scroll container
  - Apply to contacts table, calls table, contracts table, quotes table, specs table, and positions table
  - Verify no layout breaks down to 1024px viewport width
  - _Requirements: 8.1, 8.2, 8.3_

- [ ] 8. Wire updated data into page component
- [ ] 8.1 Update the customer detail page to fetch and pass contracts and org users data
  - Fetch contracts for the Documents tab content
  - Fetch organization users list for the CRM tab (call assignment)
  - Pass new data through to the appropriate tab components
  - _Requirements: 9.1, 4.1_
