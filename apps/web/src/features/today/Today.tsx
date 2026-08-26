import { useEffect, useMemo } from 'react'
import type { Account, Alert, OmniContext, Signal } from '../../types/api'
import { Button, Disclosure, Empty, EvidenceSource, Panel, State, StatTile } from '../../components/UI'
import './today.css'

const eventDate = (value?: string) => value ? new Date(value).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'Date unavailable'
const usableSource = (url: string) => /^https?:\/\//.test(url) && !url.includes('.invalid')

function commercialPriorityCounts(alerts: Alert[]) {
  return alerts.reduce((counts, alert) => {
    const severity = alert.severity.toUpperCase()
    if (severity === 'HIGH' || severity === 'MEDIUM' || severity === 'LOW') counts[severity] += 1
    return counts
  }, { HIGH: 0, MEDIUM: 0, LOW: 0 })
}

function SignalTruth({ signal }: { signal: Signal }) {
  const mode = signal.data_mode === 'CONNECTED' ? 'LIVE PUBLIC' : signal.data_mode === 'CURATED_PUBLIC' ? 'CURATED PUBLIC' : 'PUBLIC EVIDENCE'
  return <div className="truth-row"><State value={mode} /><State value={signal.resolution_state ?? signal.evidence_state} /></div>
}

export function Today({ alerts, signals, accounts, onAccount, onAction, onIntelligence, onOmniContext }: { alerts: Alert[]; signals: Signal[]; accounts: Account[]; onAccount: (id: string) => void; onAction: (alert: Alert) => void; onIntelligence: () => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) {
  const prioritySignals = useMemo(() => [...signals].sort((a, b) => (b.observed_at ?? '').localeCompare(a.observed_at ?? '')).slice(0, 4), [signals])
  const visibleRecordIds = useMemo(() => [...alerts.map(alert => alert.id), ...prioritySignals.map(signal => signal.id)].slice(0, 50), [alerts, prioritySignals])
  const counts = useMemo(() => commercialPriorityCounts(alerts), [alerts])
  const accountById = useMemo(() => new Map(accounts.map(account => [account.id, account])), [accounts])
  useEffect(() => { onOmniContext({ visible_record_ids: visibleRecordIds }) }, [onOmniContext, visibleRecordIds])
  useEffect(() => () => onOmniContext({}), [onOmniContext])
  const name = (id?: string) => accountById.get(id ?? '')?.name ?? 'Unresolved Customer'
  return <div className="surface today-surface">
    <header className="page-title today-title"><span className="eyebrow">Seller command</span><h1>Today</h1><p>What deserves attention today?</p></header>
    <section className="today-priority-summary" aria-label="Commercial review priority distribution">
      <StatTile label="High" value={counts.HIGH} detail="Commercial reviews" tone={counts.HIGH ? 'danger' : 'neutral'} />
      <StatTile label="Medium" value={counts.MEDIUM} detail="Commercial reviews" tone={counts.MEDIUM ? 'warning' : 'neutral'} />
      <StatTile label="Low" value={counts.LOW} detail="Commercial reviews" />
      <StatTile label="Public signals" value={signals.length} detail="Current governed evidence" tone="info" />
    </section>
    <div className="today-command-grid">
      <Panel title="Seller attention" action={<span className="panel-kicker">SAMPLE BTX commercial context</span>}>
        {alerts.length ? <div className="today-attention-list">{alerts.map(alert => <article className="today-attention-item" key={alert.id}>
          <div className="today-item-heading"><button className="today-customer-link" onClick={() => onAccount(alert.account_id)}>{name(alert.account_id)}</button><State value={alert.severity} /></div>
          <p><strong>Why:</strong> {alert.trigger_reason}</p><p><strong>Next:</strong> {alert.recommended_action}</p>
          <Disclosure title="SAMPLE evidence and actions"><p className="today-evidence-note">SAMPLE BTX commercial context · Evidence IDs: {alert.evidence_ids.length ? alert.evidence_ids.join(', ') : 'Unavailable'}</p><div className="card-actions"><Button onClick={() => onAccount(alert.account_id)}>Review Customer</Button><Button variant="primary" onClick={() => onAction(alert)}>Create action</Button></div></Disclosure>
        </article>)}</div> : <Empty>No commercial reviews need attention.</Empty>}
      </Panel>
      <Panel title="Public intelligence" action={<Button variant="ghost" onClick={onIntelligence}>View Intelligence</Button>}>
        {prioritySignals.length ? <div className="today-signal-list">{prioritySignals.map(signal => <article className="today-signal-item" key={signal.id}>
          <div className="today-item-heading"><button className="today-customer-link" disabled={!signal.account_id} onClick={() => signal.account_id && onAccount(signal.account_id)}>{name(signal.account_id)}</button><SignalTruth signal={signal} /></div>
          <h3>{signal.title}</h3><p><strong>Why it may matter:</strong> {signal.relevance_explanation}</p>
          <Disclosure title={`Evidence · ${eventDate(signal.observed_at)}`}><EvidenceSource title={signal.title} source={signal.source_tier} date={eventDate(signal.observed_at)} evidenceState={signal.evidence_state} validationState={signal.source_validation_state} url={usableSource(signal.source_url) ? signal.source_url : undefined} /></Disclosure>
        </article>)}</div> : <Empty>No governed public intelligence is available.</Empty>}
      </Panel>
    </div>
  </div>
}
