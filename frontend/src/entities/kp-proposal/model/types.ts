/**
 * Type definitions for a КП (commercial proposal) form snapshot.
 *
 * Field names mirror the Python `KpProposal` dataclass in
 * `services/kp_export.py` 1:1 — keeping the wire format snake_case avoids
 * any serialization mapping between the form and the FastAPI endpoint.
 *
 * Every field defaults to an empty value on the backend, so partial
 * submissions never crash the renderer.
 */

export interface KpItem {
  name: string;
  model: string;
  /** kept as a free-form string; the renderer parses defensively */
  qty: string;
  /** kept as a free-form string; the renderer parses defensively */
  price: string;
}

export interface KpPackagingItem {
  text: string;
  checked: boolean;
}

export interface KpServices {
  delivery: boolean;
  training: boolean;
  supervision: boolean;
  warranty: boolean;
  commissioning: boolean;
  service: boolean;
}

export interface KpProposal {
  subtitle: string;
  supplier: string;
  manager: string;
  phone: string;
  email: string;
  address: string;
  basis: string;
  payment: string;
  date: string;
  lead: string;
  amount: string;
  /** snake_case to match the Python `KpProposal.price_includes` field */
  price_includes: string;
  items: KpItem[];
  notes: string;
  specs: string[];
  packaging: KpPackagingItem[];
  conditions: string[];
  services: KpServices;
  notes2: string;
  contact_phone: string;
  contact_email: string;
  contact_site: string;
  contact_address: string;
  foot_phone: string;
  foot_site: string;
  foot_email: string;
}
