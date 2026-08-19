import { useEffect, useMemo, useState } from 'react'
import type { Account, OmniContext, Signal } from '../../types/api'
import { Empty, Panel, State } from '../../components/UI'

const usable = (url: string) => /^https?:\/\//.test(url) && !url.includes('.invalid')
const eventDate = (value?: string) => value ? new Date(value).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'Unavailable'

const sourceValidation = (state?: string) => ({
  BROWSER_VERIFIED: 'Source opened and supported in a normal browser.',
  AUTOMATION_BLOCKED: 'Publisher controls blocked automated validation; the original official source is retained.',
  REPLACED_WITH_EQUIVALENT_OFFICIAL_SOURCE: 'A stable, equivalent official source replaced the original; provenance retains the original.',
  NEEDS_RESEARCH: 'Source validation still needs research.',
}[state ?? ''])

export function Intelligence({ signals, accounts, onAccount, onEventSelect, onOmniContext }: { signals: Signal[]; accounts: Account[]; onAccount: (id: string) => void; onEventSelect: (id?: string) => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) {
  const [selectedEventId, setSelectedEventId] = useState<string>()
  const visibleRecordIds = useMemo(() => signals.slice(0, 50).map(signal => signal.id), [signals])
  useEffect(() => () => onEventSelect(undefined), [onEventSelect])
  useEffect(() => { onOmniContext({ visible_record_ids: visibleRecordIds }) }, [onOmniContext, visibleRecordIds])
  useEffect(() => () => onOmniContext({}), [onOmniContext])
  const selectEvent = (id: string) => setSelectedEventId(current => {
    const next = current === id ? undefined : id
    onEventSelect(next)
    return next
  })
  const name = (id?: string) => accounts.find(account => account.id === id)?.name ?? 'Unresolved company'
  return <div className="surface"><div className="page-title"><span className="eyebrow">Curated public evidence</span><h1>Intelligence</h1><p>These briefs are sourced POC research, not live collection. Recommendations stay bounded to the public evidence shown.</p></div><Panel title="Opportunity briefs" action={<span className="panel-kicker">{signals.length} curated events</span>}>{signals.length ? <div className="signal-grid">{signals.map(signal => <article className="card" key={signal.id}><div className="row"><State value="PUBLICLY VERIFIED" /><State value={signal.evidence_state} /></div><h3>{name(signal.account_id)}</h3><p><strong>What happened:</strong> {signal.title}</p><div className="meta-grid"><span>Date <strong>{eventDate(signal.observed_at)}</strong></span><span>Source type <strong>{signal.source_tier ?? 'Authoritative public source'}</strong></span><span>Why it may matter <strong>{signal.relevance_explanation}</strong></span><span>Relationship <strong>Not inferred from public evidence</strong></span></div>{sourceValidation(signal.source_validation_state) && <small className="muted">Source validation: {sourceValidation(signal.source_validation_state)}</small>}<div className="card-actions">{usable(signal.source_url) ? <a href={signal.source_url} target="_blank" rel="noreferrer">Open source ↗</a> : <span className="muted">Source unavailable</span>}<button aria-pressed={selectedEventId === signal.id} onClick={() => selectEvent(signal.id)}>{selectedEventId === signal.id ? 'Clear Omni event' : 'Use in Omni'}</button>{signal.account_id && <button onClick={() => onAccount(signal.account_id!)}>Open account</button>}</div><small>Recommended next step: review public evidence and the account’s explicit POC context.</small></article>)}</div> : <Empty>No curated public evidence is available.</Empty>}</Panel></div>
}
