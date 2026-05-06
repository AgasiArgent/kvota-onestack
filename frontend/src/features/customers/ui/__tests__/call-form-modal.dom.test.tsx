// @vitest-environment jsdom
/**
 * МОП-4 regression: a call must be addressable to a contact (contact_person_id),
 * not only to an internal employee. Earlier code dropped the saved
 * contact when re-opening the modal for editing — `contact_person_id`
 * was hardcoded to null in `buildInitialForm`. This file locks the new
 * behavior:
 *
 *   1. Edit mode pre-fills `contact_person_id` from the call row.
 *   2. Submitting the form with a contact selected forwards that ID to
 *      the mutation layer.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type {
  CustomerCall,
  CustomerContact,
} from "@/entities/customer";

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

function makeContact(overrides: Partial<CustomerContact> = {}): CustomerContact {
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

describe("CallFormModal — contact wiring (МОП-4)", () => {
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

  /** Resolve the combobox trigger sitting under a field-section label. */
  function getComboboxByLabel(labelText: string): HTMLElement {
    const label = screen.getByText(labelText);
    const wrapper = label.closest("div.space-y-1\\.5");
    if (!wrapper) throw new Error(`No wrapper for ${labelText}`);
    const trigger = wrapper.querySelector<HTMLElement>(
      '[role="combobox"]',
    );
    if (!trigger) throw new Error(`No combobox under ${labelText}`);
    return trigger;
  }

  it("forwards contact_person_id to createCall when a contact is selected for a new call", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    const contact = makeContact();

    render(
      <CallFormModal
        open
        onClose={() => {}}
        onSaved={onSaved}
        customerId="cust-1"
        contacts={[contact]}
        orgUsers={[{ id: "user-mop", full_name: "МОП Иван" }]}
        currentUserId="user-mop"
      />,
    );

    // Pick the contact in the «Контактное лицо» dropdown
    const contactTrigger = getComboboxByLabel("Контактное лицо");
    await user.click(contactTrigger);
    const option = await screen.findByRole("option", {
      name: /Анна Петрова/,
    });
    await user.click(option);

    // Submit
    await user.click(screen.getByRole("button", { name: /Сохранить/ }));

    await waitFor(() => {
      expect(createCallMock).toHaveBeenCalledTimes(1);
    });
    const [customerId, payload] = createCallMock.mock.calls[0];
    expect(customerId).toBe("cust-1");
    expect(payload).toMatchObject({ contact_person_id: "contact-1" });
  });

  it("pre-fills contact_person_id from the call row when editing", async () => {
    const user = userEvent.setup();

    render(
      <CallFormModal
        open
        onClose={() => {}}
        onSaved={() => {}}
        customerId="cust-1"
        contacts={[makeContact()]}
        orgUsers={[{ id: "user-mop", full_name: "МОП Иван" }]}
        currentUserId="user-mop"
        call={makeCall({ contact_person_id: "contact-1" })}
      />,
    );

    // The contact dropdown should already reflect the linked contact —
    // Base UI's Select trigger shows either the resolved label or the
    // raw value depending on whether the popup has been opened. Both
    // confirm the prop is wired; we only need it to NOT show the
    // placeholder.
    const contactTrigger = getComboboxByLabel("Контактное лицо");
    expect(contactTrigger).not.toHaveTextContent("Не выбрано");
    // The trigger must display either the contact id or the contact name.
    expect(contactTrigger.textContent).toMatch(/contact-1|Анна/);

    // Submit — the mutation receives the existing contact_person_id
    // even though the user did not interact with the dropdown.
    await user.click(screen.getByRole("button", { name: /Сохранить/ }));

    await waitFor(() => {
      expect(updateCallMock).toHaveBeenCalledTimes(1);
    });
    const [callId, payload] = updateCallMock.mock.calls[0];
    expect(callId).toBe("call-1");
    expect(payload).toMatchObject({ contact_person_id: "contact-1" });
  });
});
