const SALES_ROLES = ["sales", "head_of_sales"];

const NON_SALES_ROLES = [
  "admin",
  "top_manager",
  "procurement",
  "logistics",
  "customs",
  "quote_controller",
  "spec_controller",
  "finance",
  "head_of_procurement",
  "head_of_logistics",
];

/**
 * Returns true if the user has ONLY sales-type roles (sales, head_of_sales)
 * and no other operational roles that grant broader visibility.
 */
export function isSalesOnly(roles: string[]): boolean {
  return (
    roles.some((r) => SALES_ROLES.includes(r)) &&
    !roles.some((r) => NON_SALES_ROLES.includes(r))
  );
}
