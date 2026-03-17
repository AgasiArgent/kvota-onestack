# Requirements Document

## Introduction
Enhance the Next.js customer detail page based on real user feedback. Covers DB schema extensions, improved tab layouts, multi-phone contacts, call assignment, editable addresses, and contracts management. All changes target the Next.js frontend (`frontend/src/features/customers/`, `frontend/src/entities/customer/`) and Supabase database (schema `kvota`).

## Requirements

### Requirement 1: Customer General Email
**Objective:** As a sales manager, I want to store a general email address for each customer, so that I can use it for bulk mailings and official correspondence separate from individual contact emails.

#### Acceptance Criteria
1. The Customer Detail Page shall display a `general_email` field in the Реквизиты card on the Overview tab.
2. When a user clicks the general_email field, the Customer Detail Page shall enable inline editing of the value.
3. When a user saves a modified general_email, the Customer Detail Page shall persist the value to `kvota.customers.general_email`.
4. If the general_email field is empty, the Customer Detail Page shall display a placeholder "Добавить email" with muted styling.

### Requirement 2: Customer Notes on Overview Tab
**Objective:** As a sales manager, I want to see and edit customer notes directly on the Overview tab, so that important information about the counterparty is immediately visible without switching tabs.

#### Acceptance Criteria
1. The Customer Detail Page shall display the notes section on the Overview tab with inline editing capability.
2. The Customer Detail Page shall not display a notes section on the CRM tab (moved to Overview).
3. When a user edits and saves notes on the Overview tab, the Customer Detail Page shall persist changes using the existing `updateCustomerNotes` mutation.
4. While notes content is empty, the Customer Detail Page shall display a placeholder "Добавить заметки о клиенте".

### Requirement 3: Multi-Phone Contacts
**Objective:** As a sales manager, I want to store multiple phone numbers per contact with labels and extensions, so that I can reach contacts at different numbers (office, mobile, extension).

#### Acceptance Criteria
1. The Customer Detail Page shall store contact phones as a JSONB array in `kvota.customer_contacts.phones`, where each entry contains `number` (string, required), `ext` (string, optional), and `label` (string, optional).
2. When creating or editing a contact, the Contact Form shall display a dynamic list of phone fields with add/remove capability.
3. When a user adds a phone entry, the Contact Form shall show fields for number, extension (optional), and label dropdown (основной, рабочий, мобильный, добавочный).
4. The Customer Detail Page shall migrate existing `phone` column data into `phones[0]` with label "основной" via a database migration.
5. The CRM tab contacts table shall display the primary phone (first entry) with a tooltip or expandable view showing additional phones.

### Requirement 4: Call Assignment
**Objective:** As a sales manager, I want to assign a call or meeting to a specific colleague, so that tasks can be delegated to the right person.

#### Acceptance Criteria
1. When creating a call or meeting, the Call Form shall display an "Ответственный" field with a user select dropdown.
2. The Call Form shall default the assigned_to value to the current user.
3. The CRM tab calls table shall display the assigned user's name alongside the call creator.
4. When a call has an assigned_to value different from the creator, the CRM tab shall visually distinguish the assignee (e.g., "→ Иванов").

### Requirement 5: Contact Information in Call List
**Objective:** As a sales manager, I want to see contact phone and email when viewing calls, so that I can quickly reach out without navigating to the contact card.

#### Acceptance Criteria
1. The CRM tab calls table shall display the contact's primary phone number alongside the contact name.
2. When a user hovers over or expands a call row, the Customer Detail Page shall show the contact's email and additional phones.
3. If the call's contact has no phone or email, the Customer Detail Page shall display "—" in the respective column.

### Requirement 6: Editable Addresses
**Objective:** As a sales manager, I want to edit customer addresses directly in the CRM tab, so that I can update address information without backend access.

#### Acceptance Criteria
1. The CRM tab addresses section shall display an edit button for each address type (legal, actual, postal).
2. When a user clicks edit on an address, the Customer Detail Page shall switch the address card to an editable text input.
3. When a user saves an edited address, the Customer Detail Page shall persist changes using the existing `updateCustomerAddresses` mutation.
4. The CRM tab shall display an add/remove interface for warehouse addresses (JSON array field).

### Requirement 7: Positions Tab — SKU Split
**Objective:** As a procurement specialist, I want to see the article number (SKU) and IDN-SKU as separate columns, so that I can distinguish between the customer's requested article and the system-generated identifier.

#### Acceptance Criteria
1. The Positions tab table shall display `sku` (Артикул) and `idn_sku` (IDN-SKU) as two separate columns.
2. The Positions tab shall not combine or alias sku and idn_sku under a single column header.

### Requirement 8: Responsive Tables
**Objective:** As a user on any screen size, I want customer tables to remain usable on narrow viewports, so that I can work effectively on screens between 1200px and 1920px.

#### Acceptance Criteria
1. All tables on the Customer Detail Page shall support horizontal scrolling when content exceeds the viewport width.
2. While the viewport is narrower than the table's natural width, the Customer Detail Page shall display a horizontal scrollbar on the table container.
3. The Customer Detail Page shall not break layout or hide columns without scroll access on viewports down to 1024px.

### Requirement 9: Contracts Section in Documents Tab
**Objective:** As a sales manager, I want to view and manage customer contracts in the Documents tab, so that I can track contract numbers needed for downstream document generation (specifications, invoices).

#### Acceptance Criteria
1. The Documents tab shall display a "Договоры" section showing records from `kvota.customer_contracts`.
2. The Contracts section shall display: contract_number, contract_date, status (active/suspended/terminated), and notes.
3. When a user clicks "Добавить договор", the Customer Detail Page shall open a modal form with fields: contract_number (required), contract_date, status, notes.
4. When a user edits a contract, the Customer Detail Page shall open the same modal pre-filled with existing values.
5. When a user deletes a contract, the Customer Detail Page shall request confirmation before removing from `kvota.customer_contracts`.
6. The Contracts section shall display the contract status with color-coded badges (active=green, suspended=yellow, terminated=red).

### Requirement 10: Database Schema Extensions
**Objective:** As a developer, I want the database schema extended to support new features, so that the frontend has proper backing storage.

#### Acceptance Criteria
1. The database shall have a `general_email VARCHAR(255)` column on `kvota.customers`.
2. The database shall have a `phones JSONB DEFAULT '[]'` column on `kvota.customer_contacts`.
3. The database shall have an `assigned_to UUID REFERENCES auth.users(id)` column on `kvota.customer_calls`.
4. When migration 189 runs, the database shall populate `phones[0]` from existing `phone` column data with `{"number": <phone>, "ext": null, "label": "основной"}` for all contacts where phone is not null.
5. The frontend TypeScript types shall be regenerated after migrations via `npm run db:types`.
