export interface RetainedDocument {
  extraction_status: string
  extraction_complete: boolean
  completeness_note?: string
  checksum_sha256?: string
  publication_date?: string | null
  retrieved_at?: string | null
  publisher_host?: string
  final_url?: string
  retained_after_unsuccessful_refresh?: boolean
  latest_refresh_attempt?: { extraction_status: string }
  passages: Array<{ id: string; text: string; start_character: number; end_character: number }>
}

export interface PublicSourceEvidence {
  event_id: string
  title: string
  observation_id: string
  source_url: string
  content_hash: string
  availability: string
  collection_run_id: string
  document: RetainedDocument | null
  research?: {
    run_id: string
    source_revision: string
    status: string
    updated_at: string
    attempt_count: number
    steps: Array<{ number: number; tool: string; status: string; started_at: string; completed_at: string | null }>
    result: {
      status: string
      provider: string
      model: string
      published: false
      documents: Array<{ source_id: string; url: string; title: string; publisher_host: string; retrieved_at: string; publication_date: string | null; document: RetainedDocument }>
    }
  } | null
}
