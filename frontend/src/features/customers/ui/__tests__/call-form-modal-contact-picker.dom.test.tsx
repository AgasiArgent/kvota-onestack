// @vitest-environment jsdom
/**
 * МОП-4 follow-up: Call form modal must
 *
 *   1. Show a Contact picker UI (the contact_person_id data path was
 *      wired in PR #118 but the UI element was hidden whenever the
 *      customer had zero contacts → tester saw no «Контакт» field).
 *   2. Pre-fill «Ответственный» with the user's full name, not their
 *      raw UUID — Base UI's Select trigger surfaced the value verbatim
 *      until the popup was opened, which is why prod testers reported
 *      seeing «a1dc620a-8e96-41f2-b33c-8d7a7f6629cb» under «Ответственный».
 *
 * The fix replaces both Selects with the project-standard SearchableCombobox,
 * whose trigger resolves the label up-front via items.find(...).
 *
 * This file also covers the original МОП-4 regressions (PR #118):
 *   - Edit-mode pre-fill of contact_person_id from the call row.
 *   - Forwarding contact_person_id to createCall on submit.
 */
import React from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type {
  CustomerCall,
  CustomerContact,
} from "@/entities/customer";

// jsdom does not implement Element.prototype.scrollIntoView; the
// SearchableCombobox calls it in a useEffect when focus moves. Polyfill
// it locally so click-to-pick tests don't blow up before the assertion.
beforeAll(() => {
  if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
});

const createCallMock = vi.fn();
const updateCallMock = vi.fn();

vi.mock("@/entities/customer/mutations", async () => {
  const actual = await vi.importActual<
    typeof import("@/entities/customer/mutations")
  >("@/entities/customer/mutations");
  return {
    ...actual,
    createCall: (...args: unknown[]) => createCallMock(...args),
    updateCall: (...args: unknown[]) => updateCallMock(...args),
  };
});

import { CallFormModal } from "../call-form-modal";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeContact(
  overrides: Partial<CustomerContact> = {},
): CustomerContact {
  return {
    id: "contact-1",
    customer_id: "cust-1",
    name: "Анна",
    last_name: "Петрова",
    patronymic: null,
    position: "Менеджер",
    email: null,
    phone: "+7 (495) 123-45-67",
    phones: [],
    is_signatory: false,
    is_primary: true,
    is_lpr: false,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeCall(overrides: Partial<CustomerCall> = {}): CustomerCall {
  return {
    id: "call-1",
    call_type: "call",
    call_category: "warm",
    scheduled_date: null,
    comment: "Клиент просил перезвонить",
    customer_needs: null,
    meeting_notes: null,
    contact_person_id: "contact-1",
    contact_name: "Анна",
    contact_phone: "+7 (495) 123-45-67",
    contact_email: null,
    user_name: "МОП Иван",
    assigned_to: "user-mop",
    assigned_user_name: "МОП Иван",
    created_at: "2026-05-05T10:00:00Z",
    ...overrides,
  };
}

const ASSIGNED_USER_UUID = "a1dc620a-8e96-41f2-b33c-8d7a7f6629cb";
const ASSIGNED_USER_NAME = "Александр Боков";

// ---------------------------------------------------------------------------
// Helpers — find a SearchableCombobox by its sectional label.
// ---------------------------------------------------------------------------

/**
 * SearchableCombobox renders a `<button aria-label={ariaLabel}>` as the
 * popover trigger, so the easiest stable handle is the aria label we set
 * on the consumer side. Both pickers (Контактное лицо / Ответственный)
 * forward their section heading to ariaLabel.
 */
function getComboboxByAriaLabel(label: string): HTMLElement {
  return screen.getByRole("button", { name: label });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CallFormModal — contact picker UI (МОП-4 follow-up)", () => {
  beforeEach(() => {
    createCallMock.mockReset();
    updateCallMock.mockReset();
    createCallMock.mockResolvedValue({ id: "new-call" });
    updateCallMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the Контактное лицо picker even when the customer has multiple contacts", () => {
    const contactA = makeContact({
      id: "contact-1",
      name: "Анна",
      last_name: "Петрова",
      position: "Менеджер",
      phone: "+7 495 100-00-01",
    });
    const contactB = makeContact({
      id: "contact-2",
      name: "Борис",
      last_name: "Сидоров",
      position: "Закупщик",
      phone: "+7 495 100-00-02",
    });

    render(
      <CallFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
        contacts={[contactA, contactB]}
        orgUsers={[{ id: ASSIGNED_USER_UUID, full_name: ASSIGNED_USER_NAME }]}
        currentUserId={ASSIGNED_USER_UUID}
      />,
    );

    // The label and the trigger button must both be present — prod bug
    // was «no Контакт field rendered» because of a `contacts.length > 0`
    // gate on the old Select.
    expect(screen.getByText("Контактное лицо")).toBeInTheDocument();
    expect(getComboboxByAriaLabel("Контактное лицо")).toBeInTheDocument();
  });

  it("lists every contact (with name + position) inside the Контактное лицо combobox", async () => {
    const user = userEvent.setup();
    const contactA = makeContact({
      id: "contact-1",
      name: "Анна",
      last_name: "Петрова",
      position: "Менеджер",
    });
    const contactB = makeContact({
      id: "contact-2",
      name: "Борис",
      last_name: "Сидоров",
      position: "Закупщик",
    });

    render(
      <CallFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
        contacts={[contactA, contactB]}
        orgUsers={[{ id: ASSIGNED_USER_UUID, full_name: ASSIGNED_USER_NAME }]}
        currentUserId={ASSIGNED_USER_UUID}
      />,
    );

    await user.click(getComboboxByAriaLabel("Контактное лицо"));

    // Both contacts visible after open. The label format is
    // "<full name> · <position>" per getContactLabel().
    await waitFor(() => {
      expect(
        screen.getByText(/Анна Петрова · Менеджер/),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Борис Сидоров · Закупщик/),
      ).toBeInTheDocument();
    });
  });

  it("forwards contact_person_id to createCall when a contact is picked", async () => {
    const user = userEvent.setup();
    const contact = makeContact();

    render(
      <CallFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
        contacts={[contact]}
        orgUsers={[{ id: ASSIGNED_USER_UUID, full_name: ASSIGNED_USER_NAME }]}
        currentUserId={ASSIGNED_USER_UUID}
      />,
    );

    // Open the picker.
    await user.click(getComboboxByAriaLabel("Контактное лицо"));

    // The combobox row that mentions the contact's full name + position.
    const optionRow = await screen.findByText(/Анна Петрова · Менеджер/);
    await user.click(optionRow);

    // Submit.
    await user.click(screen.getByRole("button", { name: /Сохранить/ }));

    await waitFor(() => {
      expect(createCallMock).toHaveBeenCalledTimes(1);
    });
    const [customerId, payload] = createCallMock.mock.calls[0];
    expect(customerId).toBe("cust-1");
    expect(payload).toMatchObject({ contact_person_id: "contact-1" });
  });

  it("pre-fills contact_person_id when editing an existing call", async () => {
    const user = userEvent.setup();

    render(
      <CallFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
        contacts={[makeContact()]}
        orgUsers={[{ id: ASSIGNED_USER_UUID, full_name: ASSIGNED_USER_NAME }]}
        currentUserId={ASSIGNED_USER_UUID}
        call={makeCall({ contact_person_id: "contact-1" })}
      />,
    );

    // The combobox trigger must already display the resolved contact label.
    const trigger = getComboboxByAriaLabel("Контактное лицо");
    expect(trigger).toHaveTextContent(/Анна/);
    expect(trigger).not.toHaveTextContent("Не выбран");

    // Submit without interaction — payload still carries contact_person_id.
    await user.click(screen.getByRole("button", { name: /Сохранить/ }));

    await waitFor(() => {
      expect(updateCallMock).toHaveBeenCalledTimes(1);
    });
    const [callId, payload] = updateCallMock.mock.calls[0];
    expect(callId).toBe("call-1");
    expect(payload).toMatchObject({ contact_person_id: "contact-1" });
  });
});

describe("CallFormModal — Ответственный shows full name not UUID", () => {
  beforeEach(() => {
    createCallMock.mockReset();
    updateCallMock.mockReset();
    createCallMock.mockResolvedValue({ id: "new-call" });
    updateCallMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the assigned user's full name in the Ответственный trigger, not their UUID", () => {
    render(
      <CallFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
        contacts={[]}
        orgUsers={[
          { id: ASSIGNED_USER_UUID, full_name: ASSIGNED_USER_NAME },
          { id: "user-2", full_name: "Иван Иванов" },
        ]}
        currentUserId={ASSIGNED_USER_UUID}
      />,
    );

    const trigger = getComboboxByAriaLabel("Ответственный");
    // Full name must be visible at first paint — prod regression was
    // showing the raw UUID until the user clicked the dropdown.
    expect(trigger).toHaveTextContent(ASSIGNED_USER_NAME);
    expect(trigger).not.toHaveTextContent(ASSIGNED_USER_UUID);
  });

  it("shows every org user as a full-name option (not as UUIDs) inside Ответственный", async () => {
    const user = userEvent.setup();

    render(
      <CallFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
        contacts={[]}
        orgUsers={[
          { id: ASSIGNED_USER_UUID, full_name: ASSIGNED_USER_NAME },
          { id: "user-2", full_name: "Иван Иванов" },
        ]}
        currentUserId={ASSIGNED_USER_UUID}
      />,
    );

    await user.click(getComboboxByAriaLabel("Ответственный"));

    // Popover renders both names. ASSIGNED_USER_NAME also appears in the
    // trigger because it was pre-selected — so we expect 2 occurrences
    // (trigger + option) for that name and exactly 1 for the other.
    await waitFor(() => {
      expect(screen.getAllByText(ASSIGNED_USER_NAME).length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("Иван Иванов")).toBeInTheDocument();
    });

    // No raw UUID anywhere in the document — neither in the trigger nor
    // in the option rows. Prod regression was the trigger showing the
    // raw UUID; we assert against the whole rendered tree.
    expect(screen.queryByText(ASSIGNED_USER_UUID)).toBeNull();
  });
});
