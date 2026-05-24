/**
 * Zod schema mirroring `KpProposal`.
 *
 * All fields optional — the Python endpoint accepts partial bodies and
 * fills missing keys with sensible defaults. We only use this schema at
 * the submit boundary to fail fast on type drift (e.g. an item with a
 * boolean `qty`); we do NOT use it for live form validation since the
 * UI's design allows the user to leave anything blank.
 */

import { z } from "zod";

export const kpItemSchema = z.object({
  name: z.string().optional(),
  model: z.string().optional(),
  qty: z.string().optional(),
  price: z.string().optional(),
});

export const kpPackagingItemSchema = z.object({
  text: z.string().optional(),
  checked: z.boolean().optional(),
});

export const kpServicesSchema = z.object({
  delivery: z.boolean().optional(),
  training: z.boolean().optional(),
  supervision: z.boolean().optional(),
  warranty: z.boolean().optional(),
  commissioning: z.boolean().optional(),
  service: z.boolean().optional(),
});

export const kpProposalSchema = z.object({
  subtitle: z.string().optional(),
  supplier: z.string().optional(),
  manager: z.string().optional(),
  phone: z.string().optional(),
  email: z.string().optional(),
  address: z.string().optional(),
  basis: z.string().optional(),
  payment: z.string().optional(),
  date: z.string().optional(),
  lead: z.string().optional(),
  amount: z.string().optional(),
  price_includes: z.string().optional(),
  items: z.array(kpItemSchema).optional(),
  notes: z.string().optional(),
  specs: z.array(z.string()).optional(),
  packaging: z.array(kpPackagingItemSchema).optional(),
  conditions: z.array(z.string()).optional(),
  services: kpServicesSchema.optional(),
  notes2: z.string().optional(),
  contact_phone: z.string().optional(),
  contact_email: z.string().optional(),
  contact_site: z.string().optional(),
  contact_address: z.string().optional(),
  foot_phone: z.string().optional(),
  foot_site: z.string().optional(),
  foot_email: z.string().optional(),
});

export type KpProposalInput = z.infer<typeof kpProposalSchema>;
