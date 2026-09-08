export interface CrmProposal {
  proposal_id: string; action_id: string; action_version: number; commercial_revision: string
  destination_label: string; destination: 'LOCAL_SAMPLE_ONLY'; external_write: false
  mapping: Record<string, unknown>; mapping_revision: string; blockers: string[]
  payload: { title: string; description: string | null; local_owner_id: string | null; crm_owner_id: string | null; company_id: string | null; due_date: string | null; evidence_ids: string[] }
}
export interface CrmDecision { proposal_id: string; decision_id: string; decision: 'APPROVED' | 'REJECTED'; actor_id: string; decided_at: string; is_current?: boolean }
export interface CrmAttempt { proposal_id: string; attempt_id: string; decision_id: string; status: 'SAMPLE_COMPLETED' | 'SAMPLE_FAILED'; detail: string; external_write: false; attempted_at: string; replayed?: boolean }
export type CrmEvent = { actor_id: string; occurred_at: string } & (
  { kind: 'CRM_PROPOSED'; data: CrmProposal } | { kind: 'CRM_DECIDED'; data: CrmDecision } | { kind: 'CRM_SAMPLE_ATTEMPT'; data: CrmAttempt }
)
export interface CrmHistory { action_id: string; action_version: number; current_proposal_id: string; events: CrmEvent[]; earlier_event_count: number; external_write: false }
