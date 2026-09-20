import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { Button, Disclosure, LoadingStatus } from '../../components/UI'
import type { SuggestionFeedbackHistory } from '../../types/api'

export function FeedbackHistory({ name, onChanged }: { name: (id: string) => string; onChanged: () => Promise<void> }) {
  const [history, setHistory] = useState<SuggestionFeedbackHistory>()
  const [offset, setOffset] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const controller = useRef<AbortController | null>(null)
  const retryKeys = useRef(new Map<string, string>())
  useEffect(() => () => controller.current?.abort(), [])
  const load = async (next = 0) => {
    controller.current?.abort()
    const request = new AbortController(); controller.current = request
    setBusy(true); setError('')
    try {
      const value = await api.suggestionFeedbackHistory(next, request.signal)
      if (!request.signal.aborted) { setHistory(value); setOffset(next) }
    } catch { if (!request.signal.aborted) setError('Could not read your feedback history. Retry keeps your current page.') }
    finally { if (!request.signal.aborted) setBusy(false) }
  }
  const undo = async (id: string) => {
    if (busy) return
    setBusy(true); setError('')
    if (!retryKeys.current.has(id)) retryKeys.current.set(id, crypto.randomUUID())
    try {
      await api.undoSuggestionFeedbackReceipt(id, retryKeys.current.get(id)!)
      setNotice('Undo recorded for you. Earlier IDs are not guessed onto a current recommendation.')
      await onChanged(); await load(0)
    } catch { setError('Undo could not be confirmed, or newer feedback exists. Retry uses the same request; refresh history to inspect its current version.') }
    finally { setBusy(false) }
  }
  return <Disclosure title="My feedback history and earlier suggestions">
    <p>Earlier position-based suggestion IDs are retained for audit, but are not reapplied to new recommendations. Their original evidence cannot be reconstructed safely from list position.</p>
    <Button disabled={busy} onClick={() => void load(offset)}>Refresh my feedback history</Button>
    {busy && <LoadingStatus>Opening your feedback history…</LoadingStatus>}{error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {history && <><p>{history.total} private feedback events · {history.scope === 'CURRENT_USER_ONLY' ? 'Visible only to you' : ''}</p>
      <ol className="feedback-history-list">{history.items.map(item => <li key={item.id}><strong>{name(item.account_id)} · {item.reason.replaceAll('_', ' ')}</strong><p>{item.note || 'No additional note.'}</p><small>{new Date(item.created_at).toLocaleString()} · version {item.version}</small><p>{item.identity_state === 'RETIRED_UNSTABLE_ID_NOT_REAPPLIED' ? 'Earlier ID; not reapplied to current recommendations.' : 'Stable canonical recommendation ID.'}</p>{item.can_undo && <Button disabled={busy} onClick={() => void undo(item.id)}>Undo this feedback</Button>}</li>)}</ol>
      {!history.items.length && <p>No feedback events on this page.</p>}
      <Button disabled={busy || offset === 0} onClick={() => void load(Math.max(0, offset - 20))}>Previous feedback</Button>
      <Button disabled={busy || history.next_offset == null} onClick={() => void load(history.next_offset!)}>Next feedback</Button>
      {history.legacy_dismissals.length > 0 && <Disclosure title="Retained legacy dismissals"><p>These earlier IDs no longer suppress current recommendations. No account or quote identity has been guessed.</p><ul>{history.legacy_dismissals.map(item => <li key={item.suggestion_id}>{item.suggestion_id} · {new Date(item.dismissed_at).toLocaleString()}</li>)}</ul><small>Latest {history.legacy_limit} legacy records at most.</small></Disclosure>}
    </>}
  </Disclosure>
}
