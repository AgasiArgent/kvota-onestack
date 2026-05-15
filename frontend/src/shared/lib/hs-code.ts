/** Strip all non-digit chars from a ТН ВЭД / HS code.
 *  Codes are semantically 10 digits; separators (space, dot, dash) are
 *  visual formatting from reference books / copy-paste. */
export function normalizeHsCode(raw: string | null | undefined): string {
  return (raw ?? "").replace(/\D/g, "");
}
