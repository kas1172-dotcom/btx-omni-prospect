import type { CommercialDecision, CommercialDecisions } from './decisions'

export type Opportunity = Omit<CommercialDecisions['opportunities'][number], 'value_minor' | 'opportunity_priority'> & {
  value_minor: number | null
  market?: string | null
  bu?: string | null
  opportunity_priority: Omit<CommercialDecision, 'factors'> & { factors: Array<CommercialDecision['factors'][number] & { contribution?: string | number | null }> }
  gates?: {
    qualified_and_durable: boolean
    durable_best_bet: boolean
    qualification_checks?: Record<string, boolean | null>
    durability_checks?: Record<string, boolean | null>
    evidence_ids?: string[]
  }
  account_id: string
  account_name: string
  lane: 'CUSTOMER_EXPANSION' | 'PROSPECT' | 'REVIEW_REQUIRED'
  title: string
  next_action: string | null
  business_context?: string | null
  material_uncertainties: string[]
  source_record_id: string
  as_of: string
  revision: string
  attractiveness: { score: string | number | null; score_range: { low: string | number; high: string | number }; coverage: string | number; configuration_version: string; missingness: string[]; subject_id: string }
}
