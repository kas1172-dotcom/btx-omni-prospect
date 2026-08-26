import { useEffect, useMemo, useState } from 'react'
import type { Account, OmniContext, Signal } from '../../types/api'
import { Empty, EvidenceSource, Panel, State } from '../../components/UI'
import './intelligence.css'

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
  const name = (id?: string) => accounts.find(account => account.id === id)?.name ?? 'Unresolved Customer'
  const needsResearch = signals.filter(signal => signal.source_validation_state === 'NEEDS_RESEARCH').length
  const linkedAccounts = signals.filter(signal => signal.account_id && accounts.some(account => account.id === signal.account_id)).length
  return <div className="surface intelligence-surface"><div className="page-title intelligence-title"><span className="eyebrow">Curated public evidence</span><h1>Intelligence</h1><p>These briefs are sourced POC research, not live collection. Recommendations stay bounded to the public evidence shown.</p></div><div className="intelligence-summary-grid" aria-label="Intelligence summary"><article><span>Curated signals</span><strong>{signals.length}</strong><small>Canonical public events in this view</small></article><article><span>Canonical Customer links</span><strong>{linkedAccounts}</strong><small>Only supplied Customer associations count</small></article><article><span>Source review</span><strong>{needsResearch}</strong><small>Signals still marked needs research</small></article></div><Panel title="Opportunity briefs" action={<span className="panel-kicker">{signals.length} curated events · current canonical order</span>}>{signals.length ? <div className="intelligence-signal-list">{signals.map(signal => <article className={`card intelligence-signal ${selectedEventId === signal.id ? 'selected' : ''}`} key={signal.id}><div className="intelligence-signal-head"><div><span className="eyebrow">{signal.kind.replaceAll('_', ' ')}</span><h3>{name(signal.account_id)}</h3><small>{eventDate(signal.observed_at)} · {signal.source_tier ?? 'Authoritative public source'}</small></div><div className="intelligence-states"><State value="PUBLICLY VERIFIED" /><State value={signal.evidence_state} /></div></div><p className="intelligence-event"><strong>What happened:</strong> {signal.title}</p><div className="intelligence-evidence"><span><strong>Why it may matter</strong>{signal.relevance_explanation}</span><span><strong>Relationship boundary</strong>Not inferred from public evidence</span></div><EvidenceSource title={signal.title} source={signal.source_tier} date={eventDate(signal.observed_at)} evidenceState={signal.evidence_state} validationState={signal.source_validation_state} url={signal.source_url} detail={sourceValidation(signal.source_validation_state)} /><div className="card-actions intelligence-actions"><button aria-pressed={selectedEventId === signal.id} onClick={() => selectEvent(signal.id)}>{selectedEventId === signal.id ? 'Clear Omni event' : 'Use in Omni'}</button>{signal.account_id && <button onClick={() => onAccount(signal.account_id!)}>Open Customer</button>}</div><small className="intelligence-next-step">Recommended next step: review public evidence and the Customer’s explicit POC context.</small></article>)}</div> : <Empty>No curated public evidence is available.</Empty>}</Panel></div>
}
