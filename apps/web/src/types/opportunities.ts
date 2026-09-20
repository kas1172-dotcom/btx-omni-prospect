import type { CommercialDecisions } from './decisions'

export type Opportunity = CommercialDecisions['opportunities'][number] & {
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
