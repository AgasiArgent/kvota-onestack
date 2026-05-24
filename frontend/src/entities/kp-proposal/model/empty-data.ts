import type { KpProposal } from "./types";

/**
 * Blank proposal used by the "Очистить" action.
 *
 * REQ-2.4: every field becomes an empty string, every dynamic list
 * collapses to a single empty placeholder row, every checkbox is false.
 * One placeholder row keeps the form panel visually anchored — adding the
 * first item is then a question of typing into an existing row instead of
 * remembering to press "+ Добавить".
 */
export const EMPTY_PROPOSAL: KpProposal = {
  subtitle: "",
  supplier: "",
  manager: "",
  phone: "",
  email: "",
  address: "",
  basis: "",
  payment: "",
  date: "",
  lead: "",
  amount: "",
  price_includes: "",
  items: [{ name: "", model: "", qty: "", price: "" }],
  notes: "",
  specs: [""],
  packaging: [{ text: "", checked: false }],
  conditions: [""],
  services: {
    delivery: false,
    training: false,
    supervision: false,
    warranty: false,
    commissioning: false,
    service: false,
  },
  notes2: "",
  contact_phone: "",
  contact_email: "",
  contact_site: "",
  contact_address: "",
  foot_phone: "",
  foot_site: "",
  foot_email: "",
};
