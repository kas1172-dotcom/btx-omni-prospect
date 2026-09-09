export interface OmniRun {
  id: string
  started_at: string
  completed_at: string | null
  status: 'RUNNING' | 'ANSWER_RECORDED' | 'FAILED'
  operational_state: string
  request_hash: string
  result_hash: string | null
  contract_version: string
  authority: string
  result: null | {
    answer?: string
    provider?: string
    model?: string
    provider_status?: string
    failure_class?: string
    graph_revision?: string | null
    market_vintage_id?: string | null
    execution?: { external_writes: number; work_writes: number; memory_writes: number; scope: string }
    retrieval?: { revision?: string; stop_reason?: string; steps?: Array<{ step: number; tool: string; result_checksum: string; evidence_ids: string[] }> }
    provider_usage?: Array<{ receipt_id?: string; total_tokens?: number | null }>
    build?: { commit_sha: string | null; worktree: string; required_schema_revision: string }
  }
}
