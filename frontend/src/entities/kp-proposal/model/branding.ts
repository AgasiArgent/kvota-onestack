/**
 * Master Bearing branding constants for the КП preview area.
 *
 * Must stay in sync with `services/kp_branding.py:MASTER_BEARING`. The
 * preview surfaces these values directly; the renderer reads its own copy
 * from Python at render-time. Any divergence means the browser preview
 * disagrees with the generated PDF.
 *
 * Future multi-brand work: replace the constant with a lookup function
 * `getBranding(orgId)` — no changes needed in any component that just
 * imports `BRANDING`.
 */

export interface KpBranding {
  primaryBlue: string;
  primaryRed: string;
  accentCream: string;
  defaultSubtitle: string;
  footPhone: string;
  footSite: string;
  footEmail: string;
}

export const BRANDING: KpBranding = {
  primaryBlue: "#1c3e87",
  primaryRed: "#d6202a",
  accentCream: "#fbf6ec",
  defaultSubtitle: "на поставку крупной спецтехники",
  footPhone: "8-800-350-21-34",
  footSite: "www.masterbearing.ru",
  footEmail: "order@masterbearing.ru",
};
