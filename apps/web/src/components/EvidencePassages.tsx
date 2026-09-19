import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { LoadingStatus } from './UI'

export function EvidencePassages({ eventId }: { eventId: string }) {
  const [open, setOpen] = useState(false)
  const [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<Awaited<ReturnType<typeof api.intelligenceEvidence>>>()
  const [errorId, setErrorId] = useState<string>()
  const result = loaded?.event_id === eventId ? loaded : undefined
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    void api.intelligenceEvidence(eventId, controller.signal).then(value => { if (!controller.signal.aborted) { setLoaded(value); setErrorId(undefined) } }).catch(() => { if (!controller.signal.aborted) setErrorId(eventId) })
    return () => controller.abort()
  }, [eventId, open, retry])
  return <details open={open} onToggle={event => setOpen(event.currentTarget.open)}><summary>Inspect retained public passages</summary>{open && <>
    {errorId === eventId ? <p role="alert">Stored passages are unavailable for this event. The source link remains available. <button type="button" onClick={() => setRetry(value => value + 1)}>Retry passages</button></p> : result ? <>
      <p><strong>{result.title}</strong></p>
      <p>{result.document?.extraction_status.replaceAll('_', ' ') ?? 'No document retrieval was recorded for this source.'}</p>
      {result.document?.retained_after_unsuccessful_refresh && <p role="status">Showing previously retrieved evidence. The latest refresh did not reverify this article ({result.document.latest_refresh_attempt?.extraction_status.replaceAll('_', ' ')}); the original retrieval date is retained.</p>}
      {result.document && <><p>{result.document.publisher_host} · published {result.document.publication_date ?? 'unknown'} · retrieved {result.document.retrieved_at ?? 'not attempted'}</p><p>{result.document.completeness_note ?? 'No complete document extraction is asserted.'}</p>
        {result.document.passages.map(passage => <details key={passage.id}><summary>Passage · characters {passage.start_character}–{passage.end_character}</summary><blockquote style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{passage.text}</blockquote><small>{passage.id}</small></details>)}
        <small style={{ overflowWrap: 'anywhere' }}>Document SHA-256 {result.document.checksum_sha256 ?? 'unavailable'}</small></>}
      <p><small>Collection run {result.collection_run_id} · observation {result.observation_id}</small></p>
      {result.research && <section aria-label="Public investigation evidence" style={{ overflowWrap: 'anywhere' }}>
        <h4>Follow-up investigation</h4>
        <p>{result.research.status === 'COMPLETED' ? 'Research collection recorded' : 'Partial research retained'} · {result.research.result.status.replaceAll('_', ' ')}</p>
        <p>Retrieved sources can support attributed public claims. Research collection alone does not qualify a prospect or establish a BTX order.</p>
        {result.research.result.documents.map(source => <details key={source.source_id}>
          <summary>{source.title}</summary>
          <p><a href={source.url} target="_blank" rel="noreferrer">Open {source.publisher_host} source</a> · published {source.publication_date ?? 'unknown'} · retrieved {source.retrieved_at}</p>
          <p>{source.document.completeness_note ?? source.document.extraction_status.replaceAll('_', ' ')}</p>
          {source.document.passages.map(passage => <details key={passage.id}><summary>Research passage · characters {passage.start_character}–{passage.end_character}</summary><blockquote style={{ whiteSpace: 'pre-wrap' }}>{passage.text}</blockquote><small>{passage.id}</small></details>)}
          <small>Document SHA-256 {source.document.checksum_sha256 ?? 'unavailable'}</small>
        </details>)}
        <details><summary>Investigation steps and lineage</summary>
          <p>{result.research.result.provider} · {result.research.result.model} · run {result.research.run_id}</p>
          <p>Source revision {result.research.source_revision} · attempts {result.research.attempt_count}</p>
          <ol>{result.research.steps.map(step => <li key={step.number}>{step.tool.replaceAll('_', ' ')} · {step.status.replaceAll('_', ' ')} · {step.completed_at ?? 'completion unknown'}</li>)}</ol>
        </details>
      </section>}
    </> : <LoadingStatus>Opening retained source passages…</LoadingStatus>}
  </>}</details>
}
