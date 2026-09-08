export interface OmniMemoryInput {
  account_id: string | null; kind: 'ANSWER_STYLE' | 'WORK_PREFERENCE'; content: string; ttl_days: number
}
export interface OmniMemory {
  id: string; account_id: string | null; kind: OmniMemoryInput['kind']; content: string; version: number
  expires_at: string; created_at: string; updated_at: string; expired?: boolean
  create_replayed?: boolean
}
