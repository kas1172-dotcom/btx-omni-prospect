import type { ActionPriority } from './api'

export interface CommercialDecision {
  decision_id: string; family: string; subject_id: string; as_of: string; revision: string
  configuration_version: string; score: string | number | null; status: string
  rule_version?: string; weighted_score?: string | number | null; weighted_band?: string; band?: string
  what_would_change_result?: string[]; calculation_trace?: Record<string, unknown>
  score_range?: { low: string | number; high: string | number }
  priority_rank?: number; priority_class?: number
  interpretation: string; eligibility_reasons: string[]; blocking_constraints: string[]
  factors: Array<{ key: string; points: string | number | null; raw_value?: string | number | null; period?: string | null; reason: string; weight: number; evidence_ids: string[]; required_fields: string[]; observed_fields: string[] }>
  data_coverage: { present: number; applicable: number; ratio: string | number; missing_fields: string[] }
}
export interface CommercialDecisions {
  customer_health: CommercialDecision; internal_commercial_risk: CommercialDecision
  public_risk_rollup: { score: string | number | null; independent_event_ids: string[]; uplift: string | number; configuration_version?: string }
  overall_customer_risk: { family: string; configuration_version: string; status: string; score: string | number | null; score_range?: { low: string | number; high: string | number }; band?: string; calculation_trace?: Record<string, unknown>; weights: Record<string, number>; convergence_uplift: string | number; missing_fields: string[]; interpretation: string }
  public_risk_events: Array<{ active: boolean; severity: string | number; underlying_event_id: string; risk_domain: string }>
  confirmed_public_event_ids: string[]
  opportunities: Array<{ opportunity_id: string; component_id: string; stage: string; value_minor: number; currency: string; qualification_status: string; durability_status: string; opportunity_priority: CommercialDecision; pwin: CommercialDecision; delivery_feasibility: CommercialDecision }>
  action_priorities: Array<{ action_id: string; title: string; work_status: string; linked_work_ids: string[]; evidence_ids: string[]; decision: CommercialDecision }>
}
export interface FollowupPreview {
  preview_token: string; revision: string; destination: string; external_write: boolean; note: string
  existing_work_id: string | null; existing_work_status: string | null
  proposal: { account_id: string; title: string; description: string | null; owner_id: string; priority: ActionPriority; due_date: string | null; evidence_ids: string[]; approval_required: boolean }
}
