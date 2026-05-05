import { describe, it, expect } from "vitest";

import { ROLE_LABELS } from "../chat-message";

/**
 * Regression test for fix/rop-test/chat-role-labels-complete.
 *
 * Field reports РОЗ-39 / МОЗ-35 / МОП-4-6-7 / РОП-4-6 (2026-05-05): the role
 * badge in chat-message bubbles rendered the raw English slug
 * («procurement_senior», «currency_controller», ...) for users whose role was
 * missing from chat-message.tsx's local label map.
 *
 * The fix is to ensure ROLE_LABELS covers every active role slug in the
 * system. This test asserts every known slug has a non-empty Russian
 * translation that is NOT the raw slug itself.
 *
 * The list mirrors `kvota.roles` (DB) + active roles consumed elsewhere in
 * the frontend (`entities/user/types.ts` ACTIVE_ROLES + `training_manager` +
 * `currency_controller`). Update both this list and ROLE_LABELS together.
 */

const KNOWN_ROLE_SLUGS = [
  "admin",
  "top_manager",
  "sales",
  "head_of_sales",
  "procurement",
  "procurement_senior",
  "head_of_procurement",
  "logistics",
  "head_of_logistics",
  "customs",
  "head_of_customs",
  "finance",
  "head_of_finance",
  "currency_controller",
  "quote_controller",
  "spec_controller",
  "training_manager",
] as const;

const RUSSIAN_LETTER = /[А-Яа-яЁё]/;

describe("chat-message ROLE_LABELS", () => {
  it.each(KNOWN_ROLE_SLUGS)(
    "has a Russian label for slug '%s'",
    (slug) => {
      const label = ROLE_LABELS[slug];

      expect(label, `ROLE_LABELS missing entry for '${slug}'`).toBeDefined();
      expect(label, `ROLE_LABELS['${slug}'] must be non-empty`).not.toBe("");
    },
  );

  it.each(KNOWN_ROLE_SLUGS)(
    "label for '%s' does not fall back to the raw slug",
    (slug) => {
      const label = ROLE_LABELS[slug];

      expect(
        label,
        `ROLE_LABELS['${slug}'] is the raw English slug — user will see it as a fallback`,
      ).not.toBe(slug);
    },
  );

  it.each(KNOWN_ROLE_SLUGS)(
    "label for '%s' contains at least one Cyrillic character",
    (slug) => {
      const label = ROLE_LABELS[slug];

      expect(
        RUSSIAN_LETTER.test(label),
        `ROLE_LABELS['${slug}'] = '${label}' is not in Russian`,
      ).toBe(true);
    },
  );
});
