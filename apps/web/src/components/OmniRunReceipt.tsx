import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { OmniRun } from '../types/omniRun'

export function OmniRunReceipt({ id }: { id: string }) {
  const [record, setRecord] = useState<OmniRun>()
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void api.omniRun(id, controller.signal).then(value => { if (!controller.signal.aborted) { setRecord(value); setError(false) } })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [id, retry])
  if (error) return <div role="alert">This private run receipt could not be loaded. The displayed answer is unchanged. <button onClick={() => { setError(false); setRetry(value => value + 1) }}>Retry run receipt</button></div>
  if (!record || record.id !== id) return <p role="status">Loading your run receipt…</p>
  return <div className="commercial-evidence-detail">
    <p>{record.operational_state.replaceAll('_', ' ').toLowerCase()} · {record.started_at}</p>
    <p>{record.authority}</p>
    <dl><div><dt>Run</dt><dd>{record.id}</dd></div><div><dt>Provider</dt><dd>{record.result?.provider ?? 'Not recorded'} · {record.result?.model ?? 'No model'} · {record.result?.provider_status ?? record.status}</dd></div>
      <div><dt>Source revision</dt><dd>{record.result?.retrieval?.revision ?? 'Not applicable'}</dd></div>
      <div><dt>Build</dt><dd>{record.result?.build?.commit_sha ?? 'Unverified'} · {record.result?.build?.worktree ?? 'unknown'}</dd></div>
      <div><dt>Answer checksum</dt><dd>{record.result_hash ?? 'No completed answer'}</dd></div></dl>
    {record.result?.execution && <p>This request recorded {record.result.execution.external_writes} external writes, {record.result.execution.work_writes} local work changes and {record.result.execution.memory_writes} preference changes. Separate approved workflows are not executed by this answer.</p>}
    <ol>{record.result?.retrieval?.steps?.map(step => <li key={step.step}>{step.tool.replaceAll('_', ' ')}<details><summary>Read evidence and checksum</summary><p>{step.evidence_ids.join(', ') || 'No linked record IDs'}</p><p>{step.result_checksum}</p></details></li>)}</ol>
    {record.result?.answer && <details><summary>Recorded answer</summary><p style={{ whiteSpace: 'pre-wrap' }}>{record.result.answer}</p></details>}
  </div>
}
