/**
 * Response shape for GET /api/quotes/{id}/cost-analysis.
 * Mirrors api/cost_analysis.py._map_totals / _logistics_breakdown / _derived_metrics.
 */

export interface CostAnalysisQuote {
  id: string;
  idn_quote: string;
  title: string;
  currency: string;
  workflow_status: string;
  customer_name: string;
}

export interface CostAnalysisTotals {
  revenue_no_vat: number;
  revenue_with_vat: number;
  purchase: number;
  logistics: number;
  customs: number;
  excise: number;
  dm_fee: number;
  forex: number;
  financial_agent_fee: number;
  financing: number;
}

export interface CostAnalysisLogisticsBreakdown {
  W2_supplier_hub: number;
  W3_hub_customs: number;
  W4_customs_client: number;
  W5_brokerage_hub: number;
  W6_brokerage_customs: number;
  W7_warehousing: number;
  W8_documentation: number;
  W9_extra: number;
  W10_insurance: number;
}

export interface CostAnalysisDerived {
  direct_costs: number;
  gross_profit: number;
  financial_expenses: number;
  net_profit: number;
  markup_pct: number;
  sale_purchase_ratio: number;
}

export interface CostAnalysisView {
  quote: CostAnalysisQuote;
  has_calculation: boolean;
  totals: CostAnalysisTotals;
  logistics_breakdown: CostAnalysisLogisticsBreakdown;
  derived: CostAnalysisDerived;
}

/** Role slugs permitted to read cost-analysis — must match the backend. */
export const COST_ANALYSIS_ROLES = [
  "finance",
  "top_manager",
  "admin",
  "quote_controller",
] as const;

export type CostAnalysisRole = (typeof COST_ANALYSIS_ROLES)[number];
