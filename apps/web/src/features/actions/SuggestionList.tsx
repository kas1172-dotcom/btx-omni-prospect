import { useRef, useState } from 'react'
import { api } from '../../api/client'
import { Button, Disclosure, Empty, Panel, SelectInput, StatusBadge, Textarea } from '../../components/UI'
import type { Suggestion, SuggestionFeedbackInput, SuggestionFeedbackReason } from '../../types/api'
import { FeedbackHistory } from './FeedbackHistory'

const reasons: Record<SuggestionFeedbackReason, string> = {
  WRONG_ACCOUNT: 'Wrong account — request review', SNOOZE: 'Snooze', ALREADY_DONE: 'Already done — personal report',
  NOT_RELEVANT: 'Not relevant to me', UNDO: 'Restored',
}
type Draft = { reason: Exclude<SuggestionFeedbackReason, 'UNDO'>; note: string; days: string }
const emptyDraft: Draft = { reason: 'NOT_RELEVANT', note: '', days: '7' }

export function SuggestionList({ suggestions, name, onConvert, onFeedback, onRefreshed }: {
  suggestions: Suggestion[]; name: (id: string) => string; onConvert: (item: Suggestion) => Promise<void>
  onFeedback: (id: string, patch: Partial<Suggestion>) => void
  onRefreshed: (items: Suggestion[]) => void
}) {
  const [view, setView] = useState('ACTIVE')
  const [editing, setEditing] = useState<string>()
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [busy, setBusy] = useState<string>()
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const inFlight = useRef(false)
  // Preserve the exact request (including snooze timestamp) across uncertain retries.
  const retry = useRef<{ signature: string; payload: SuggestionFeedbackInput } | null>(null)
  const visible = suggestions.filter(item => view === 'ALL' || (view === 'HIDDEN' ? item.dismissed : !item.dismissed))
  const changeDraft = (id: string, patch: Partial<Draft>) => setDrafts(previous => ({ ...previous, [id]: { ...(previous[id] ?? emptyDraft), ...patch } }))

  const save = async (item: Suggestion, undo = false) => {
    if (inFlight.current) return
    const draft = drafts[item.id] ?? emptyDraft
    const reason = undo ? 'UNDO' : draft.reason
    if (!undo && ['WRONG_ACCOUNT', 'ALREADY_DONE'].includes(reason) && !draft.note.trim()) {
      setError('Add the correction or completion source so your report can be reviewed.'); return
    }
    const signature = JSON.stringify([item.id, item.revision, item.feedback?.id ?? null, reason, undo ? '' : draft.note, draft.days])
    if (retry.current?.signature !== signature) retry.current = { signature, payload: {
      reason, note: undo ? '' : draft.note, expected_feedback_id: item.feedback?.id ?? null, expected_revision: item.revision,
      idempotency_key: crypto.randomUUID(),
      ...(reason === 'SNOOZE' ? { snooze_until: new Date(Date.now() + Number(draft.days) * 86400000).toISOString() } : {}),
    } }
    inFlight.current = true; setBusy(item.id); setError(''); setNotice('')
    try {
      const result = await api.suggestionFeedback(item.id, retry.current.payload)
      onFeedback(item.id, { feedback: result.current, dismissed: result.current.hidden })
      retry.current = null; setEditing(undefined)
      setNotice(result.current.source_changed ? 'Your earlier feedback receipt is preserved. The recommendation changed and is visible again for review; no new feedback was applied.' : result.current.hidden ? 'Saved for you only. Review hidden suggestions to edit or undo. Account facts, scores and Action status are unchanged.' : 'Suggestion restored for you. Account facts, scores and Action status are unchanged.')
    } catch (caught) {
      setError(`${caught instanceof Error ? caught.message : 'Feedback could not be confirmed.'} Retry keeps the same request. Refresh suggestions if another update changed this record.`)
    } finally { inFlight.current = false; setBusy(undefined) }
  }

  const refresh = async () => {
    if (inFlight.current) return
    inFlight.current = true; setBusy('refresh'); setError('')
    try {
      const response = await api.actions()
      onRefreshed(response.suggestions)
      setNotice('Suggestions refreshed. Your draft is retained.')
    } catch { setError('Could not refresh the selected suggestion. Your draft is retained.') }
    finally { inFlight.current = false; setBusy(undefined) }
  }

  const convert = async (item: Suggestion) => {
    if (inFlight.current) return
    inFlight.current = true; setBusy(item.id)
    try { await onConvert(item) } finally { inFlight.current = false; setBusy(undefined) }
  }

  return <Panel title="Suggested work" action={<span className="panel-kicker">Recommendations are not Actions</span>}>
    <div className="suggestion-feedback-toolbar"><SelectInput label="Suggestion visibility" value={view} disabled={Boolean(busy)} onChange={event => setView(event.target.value)}>
      <option value="ACTIVE">Active suggestions</option><option value="HIDDEN">Hidden and snoozed for me</option><option value="ALL">All suggestions and my feedback</option>
    </SelectInput><Button disabled={Boolean(busy)} onClick={() => void refresh()}>Refresh suggestions</Button><p>Feedback changes only your suggestion visibility. Reports are not verified corrections or completed Actions.</p></div>
    {notice ? <p role="status" className="notice">{notice}</p> : null}
    {error ? <div role="alert"><p>{error}</p><Button disabled={Boolean(busy) || !editing} onClick={() => void refresh()}>Refresh selected suggestion</Button></div> : null}
    <FeedbackHistory name={name} onChanged={refresh} />
    <div className="suggestion-list">{visible.length ? visible.map(item => {
      const draft = drafts[item.id] ?? emptyDraft
      return <article className="suggestion-card" key={item.id} data-suggestion-id={item.id}>
        <div><span className="eyebrow">{name(item.account_id)}</span><h3>{item.title}</h3><p>{item.rationale}</p></div>
        <StatusBadge value={item.priority} kind="priority" />
        <Disclosure title="Evidence references"><p>{item.evidence_ids.length ? item.evidence_ids.join(', ') : 'Unavailable'}</p></Disclosure>
        {item.feedback ? <div className="suggestion-feedback-receipt"><strong>My feedback: {reasons[item.feedback.reason]}</strong>
          {item.feedback.source_changed ? <p>The underlying recommendation changed or its earlier version was not recorded. This feedback is retained in history but no longer hides it. Review the current evidence before applying new feedback.</p> : null}
          {item.feedback.note ? <p>{item.feedback.note}</p> : null}
          <small>Saved {new Date(item.feedback.created_at).toLocaleString()} · version {item.feedback.version}</small>
          {item.feedback.snooze_until ? <p>{item.feedback.hidden ? 'Snoozed until' : 'Snooze ended'} {new Date(item.feedback.snooze_until).toLocaleString()}</p> : null}
          {item.feedback.reason === 'WRONG_ACCOUNT' ? <p>Unverified attribution report retained for review; the canonical account has not changed.</p> : null}
        </div> : null}
        <div className="card-actions">
          {item.converted_action_id ? <StatusBadge value="CONVERTED" kind="action" /> : item.conversion_blocked ? <p>Existing work needs authorized review before another Action is created.</p> : !item.dismissed ? <Button variant="primary" disabled={Boolean(busy)} onClick={() => void convert(item)}>Create Action</Button> : null}
          <Button disabled={Boolean(busy)} onClick={() => {
            if (!drafts[item.id] && item.feedback) changeDraft(item.id, { reason: item.feedback.reason === 'UNDO' ? 'NOT_RELEVANT' : item.feedback.reason, note: item.feedback.note })
            setEditing(item.id); setError('')
          }}>{item.feedback ? 'Edit my feedback' : 'Give feedback'}</Button>
          {(item.feedback && item.feedback.reason !== 'UNDO') || (item.dismissed && !item.feedback) ? <Button disabled={Boolean(busy)} onClick={() => { setEditing(item.id); void save(item, true) }}>Undo my feedback</Button> : null}
        </div>
        {editing === item.id ? <form className="suggestion-feedback-form" onSubmit={event => { event.preventDefault(); void save(item) }}>
          <SelectInput label="Feedback reason" disabled={Boolean(busy)} value={draft.reason} onChange={event => changeDraft(item.id, { reason: event.target.value as Draft['reason'] })}>
            {Object.entries(reasons).filter(([reason]) => reason !== 'UNDO').map(([reason, text]) => <option key={reason} value={reason}>{text}</option>)}
          </SelectInput>
          <Textarea label="Correction or completion source / optional note" maxLength={500} required={['WRONG_ACCOUNT', 'ALREADY_DONE'].includes(draft.reason)} disabled={Boolean(busy)} value={draft.note} onChange={event => changeDraft(item.id, { note: event.target.value })} />
          {draft.reason === 'SNOOZE' ? <SelectInput label="Snooze duration" disabled={Boolean(busy)} value={draft.days} onChange={event => changeDraft(item.id, { days: event.target.value })}>
            <option value="1">1 day</option><option value="7">7 days</option><option value="30">30 days</option>
          </SelectInput> : null}
          <div className="card-actions"><Button type="submit" variant="primary" disabled={Boolean(busy)}>{busy === item.id ? 'Saving…' : 'Save my feedback'}</Button><Button type="button" disabled={Boolean(busy)} onClick={() => setEditing(undefined)}>Close feedback</Button></div>
        </form> : null}
      </article>
    }) : <Empty>No suggestions in this view. Choose all suggestions to inspect your feedback.</Empty>}</div>
  </Panel>
}
