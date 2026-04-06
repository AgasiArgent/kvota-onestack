# Requirements Document

## Introduction

Enhance the `/admin/feedback` list page to support inline ticket triage without page navigation. Admin users need to view ticket details, change statuses, and perform bulk operations directly from the list — reducing the click overhead of the current navigate-to-detail-page workflow. The page should also support configurable pagination to handle varying volumes of feedback.

## Requirements

### Requirement 1: Inline Row Expansion

**Objective:** As an admin, I want to view feedback ticket details inline by clicking a row, so that I can triage tickets without navigating away from the list.

#### Acceptance Criteria

1. When the admin clicks a feedback row (outside interactive elements), the Feedback List shall display an expanded detail panel directly below the clicked row showing: full description, page URL, screenshot with lightbox, collapsible debug context, and ClickUp link.
2. When the admin clicks an already-expanded row, the Feedback List shall collapse the expanded detail panel.
3. When the admin clicks a different row while one is already expanded, the Feedback List shall collapse the previously expanded row and expand the newly clicked row.
4. When the admin presses Enter or Space on a focused row, the Feedback List shall toggle the expansion state of that row.
5. While a row is expanded, the Feedback List shall render all detail content from the existing detail view except the status change card (status is handled inline in the table).

### Requirement 2: Inline Status Change

**Objective:** As an admin, I want to change a ticket's status directly from the list via a dropdown, so that I can update statuses without opening the detail view.

#### Acceptance Criteria

1. The Feedback List shall display a status dropdown (Select component) in the Status column of each row instead of a static badge.
2. When the admin changes the status value in a row's dropdown, the Feedback List shall optimistically update the displayed status and call the status update API in the background.
3. If the status update API call fails, the Feedback List shall revert the status to its previous value and display an error toast notification.
4. When the admin interacts with the status dropdown, the Feedback List shall not trigger row expansion or collapse (event propagation must be stopped).

### Requirement 3: Bulk Status Change

**Objective:** As an admin, I want to select multiple tickets and change their status at once, so that I can efficiently close or update batches of tickets during triage.

#### Acceptance Criteria

1. The Feedback List shall display a checkbox column as the first column, with individual row checkboxes and a header checkbox.
2. When the admin clicks the header checkbox, the Feedback List shall select or deselect all rows on the current page.
3. While one or more rows are selected, the Feedback List shall display a bulk action toolbar between the filter tabs and the table showing: selected count, a status dropdown, an "Apply" button, and a "Clear selection" button.
4. While no status is chosen in the bulk toolbar, the Feedback List shall disable the "Apply" button.
5. When the admin clicks "Apply" with a status selected, the Feedback List shall update all selected tickets to the chosen status via a single bulk API call.
6. When the bulk status update succeeds, the Feedback List shall clear the selection, refetch the page data, and display a success toast.
7. If the bulk status update fails, the Feedback List shall display an error toast and keep the current selection intact.

### Requirement 4: Configurable Page Size

**Objective:** As an admin, I want to choose how many tickets are displayed per page (25, 50, or 100), so that I can control the density of the list based on my triage needs.

#### Acceptance Criteria

1. The Feedback List shall display a page size selector near the pagination controls with options: 25, 50, and 100.
2. The Feedback List shall default to 50 items per page.
3. When the admin changes the page size, the Feedback List shall reset to page 1 and reload data with the new page size.
4. The Feedback List shall persist the selected page size in the URL search parameters (`pageSize`).
5. When the admin changes the page size while rows are selected, the Feedback List shall clear the selection.

### Requirement 5: Preserved Functionality

**Objective:** Ensure all existing feedback list features continue to work unchanged alongside the new enhancements.

#### Acceptance Criteria

1. The Feedback List shall preserve the existing status filter tabs (All, New, In Progress, Resolved, Closed) with their current behavior.
2. The Feedback List shall preserve the debounced search input with its current filtering behavior.
3. The Feedback List shall preserve the ClickUp link column with external link behavior (stopPropagation to avoid row expansion).
4. The `/admin/feedback/[id]` detail page shall remain functional as a standalone deep link, unchanged by this enhancement.
