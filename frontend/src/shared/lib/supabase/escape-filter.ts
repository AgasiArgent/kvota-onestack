/**
 * Escape PostgREST special characters in user input for use in .or() filter strings.
 * Prevents filter injection via commas, dots, parentheses, etc.
 */
export function escapePostgrestFilter(value: string): string {
  return value.replace(/[%,().*\\]/g, (ch) => `\\${ch}`);
}
