import type { Alert } from './api'
import type { CommercialDecision } from './decisions'

export interface MonthlyCommercial {
  period: string; snapshot_id: string; currency: string; bookings_minor: number
  revenue_minor: number; closing_backlog_minor: number; provenance: Record<string, unknown>
}
export interface ProfileListFields {
  owner_id: string | null; business_unit_ids: string[]
  naics: Array<{ code: string; primary: boolean; verification: string; taxonomy_version: string; scope: string }>
  health_band: string | null; health_band_state: string
  open_items: { public: number; internal: number }
  bookings_monthly: Array<Pick<MonthlyCommercial, 'period' | 'snapshot_id' | 'currency' | 'bookings_minor' | 'provenance'>>
  bookings_delta_3m_vs_prior_3m: string | null; last_activity_at: string | null
}
export interface FunctionCoverage {
  function: string; state: 'Present' | 'Thin' | 'Missing' | 'Unknown'; role_ids: string[]
  last_two_way_at: string | null; verification_scope: string[]; source_state: string
}
export interface ProfileProjection extends ProfileListFields {
  backlog_months: string | null; quote_overdue_share: string | null
  concentration: { share: string | null; evidence: Record<string, unknown> | null }
  open_order_count: number | null; open_order_value_minor: number | null
  fulfillment: { currency: string; as_of: string; lines: Array<{ order_id: string; order_line_id: string; ordered_quantity: number; shipped_quantity: number; cancelled_quantity: number; remaining_quantity: number; committed_date: string | null; overdue: boolean; execution_status: string; evidence_ids: string[] }>; recorded_history_totals: Record<string, number> } | null
  function_coverage: FunctionCoverage[]; last_two_way_at: string | null; expected_touch_days: number | null
  internal_commercial_risk: CommercialDecision | null
  public_risk_rollup: { score: string | number | null; interpretation?: string }
  public_risk_events: Array<{ underlying_event_id: string; active: boolean; severity: string | number; risk_domain: string }>
  overall_customer_risk: { score: string | number | null; status: string; interpretation: string; missing_fields: string[] }
  open_internal_items: Alert[]; expansion_opportunity_count: number | null
}
export interface CommercialLedger {
  as_of: string; currency: string; revision: string
  ttm: { revenue_minor: number; bookings_minor: number; closing_backlog_minor: number; period_start: string; period_end: string }
  monthly_history: MonthlyCommercial[]; record_counts: Record<string, number>
}
