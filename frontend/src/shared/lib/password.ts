/** Characters used for generated passwords. Excludes ambiguous glyphs (0/O, 1/l/I). */
export const PASSWORD_CHARSET =
  "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%";

/** Generate a 12-character random password using the Web Crypto API. */
export function generatePassword(): string {
  const array = new Uint8Array(12);
  crypto.getRandomValues(array);
  return Array.from(
    array,
    (byte) => PASSWORD_CHARSET[byte % PASSWORD_CHARSET.length]
  ).join("");
}
