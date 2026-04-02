export interface OrganizationInfo {
  id: string;
  name: string;
}

export interface CalcSettings {
  id: string;
  organization_id: string;
  rate_forex_risk: number;
  rate_fin_comm: number;
  rate_loan_interest_daily: number;
}

export interface StageDeadline {
  id: string;
  organization_id: string;
  stage: string;
  deadline_hours: number;
}

export interface SettingsPageData {
  organization: OrganizationInfo;
  calcSettings: CalcSettings | null;
  stageDeadlines: StageDeadline[];
}
