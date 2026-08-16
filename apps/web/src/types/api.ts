export type Relationship = 'CURRENT_CUSTOMER' | 'TARGET'

export interface Account { id: string; name: string; relationship: Relationship; industries: string[]; provenance?: string }
export interface Alert { id: string; account_id: string; type: string; severity: string; trigger_reason: string; recommended_action: string; evidence_ids: string[]; status: string }
export interface Signal { id: string; kind: string; title: string; source_url: string; account_id?: string; program_name?: string; evidence_state: string; relevance_explanation: string; evidence_ids: string[] }
export interface WorkItem { id: string; account_id: string; status: string; summary: string; owner_id?: string; priority: string; evidence_ids: string[] }
export interface MapRecord { account_id: string; industry: string; relationship: Relationship; latitude: string; longitude: string; external_rank: number; deep_account: boolean; nearest_btx_facility: { name: string }; proximity_input: string }
export interface Account360 { account: Account; prism_commercial_context: unknown[]; paperless_quotes: Array<{ id: string; status: string; value_minor?: number; quoted_at: string }>; crm: { owner_id: string; deal_ids: string[]; activity_ids: string[] } | null; account_attractiveness: { score: string | null; coverage: string; missingness: string[] }; alerts: Alert[]; intelligence: Signal[]; matching: Array<{ method: string; review_state: string; evidence_ids: string[] }>; provenance: { source_record_id: string; evidence_state: string }; missingness: string[] }
export interface OmniResponse { content: string; citations: string[]; provenance: string[]; missingness: string[]; recommended_action?: string }
