import { useEffect, useMemo } from 'react'
import type { Account, Alert, OmniContext, Signal } from '../../types/api'
import { Empty, Panel, State } from '../../components/UI'
import './today.css'

function SignalTruth({ signal }: { signal: Signal }) {
  return <div className="truth-row"><State value={signal.data_mode === 'CONNECTED' ? 'LIVE_PUBLIC' : signal.data_mode === 'CURATED_PUBLIC' ? 'CURATED PUBLIC' : 'SIMULATED DEMO'} /><State value={signal.resolution_state ?? signal.evidence_state} /></div>
}

function SummaryCard({ label, value, detail, state }: { label: string; value: number; detail: string; state: string }) {
  return <article className="today-summary-card"><div className="today-summary-heading"><span>{label}</span><State value={state} /></div><strong>{value}</strong><small>{detail}</small></article>
}

export function Today({ alerts, signals, accounts, onAccount, onAction, onOmniContext }: { alerts: Alert[]; signals: Signal[]; accounts: Account[]; onAccount: (id: string) => void; onAction: (alert: Alert) => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) {
  const live = useMemo(() => signals.filter(signal => signal.data_mode === 'CONNECTED'), [signals])
  const priority = useMemo(() => [...live, ...signals.filter(signal => signal.data_mode !== 'CONNECTED')], [live, signals])
  const visibleRecordIds = useMemo(() => [...alerts.map(alert => alert.id), ...priority.map(signal => signal.id)].slice(0, 50), [alerts, priority])

  useEffect(() => { onOmniContext({ visible_record_ids: visibleRecordIds }) }, [onOmniContext, visibleRecordIds])
  useEffect(() => () => onOmniContext({}), [onOmniContext])

  const name = (id?: string) => accounts.find(account => account.id === id)?.name ?? 'Unresolved Customer'
  const publicDetail = live.length ? `${live.length} current live public observation${live.length === 1 ? '' : 's'}` : 'Curated public evidence in the current POC'

  return <div className="surface today-surface"><div className="page-title today-title"><span className="eyebrow">Seller command</span><h1>Today</h1><p>What changed, why it matters, and a reviewable next step—separated by source truth.</p></div><div className="today-summary-grid" aria-label="Today summary"><SummaryCard label="Commercial reviews" value={alerts.length} detail="Current SAMPLE commercial context" state="SAMPLE" /><SummaryCard label="Public signals" value={priority.length} detail={publicDetail} state={live.length ? 'LIVE_PUBLIC' : 'CURATED PUBLIC'} /><SummaryCard label="Current page scope" value={visibleRecordIds.length} detail="Bounded canonical records available to Omni" state="AVAILABLE" /></div><div className="today-workspace"><Panel title="Review next" action={<span className="panel-kicker">Current SAMPLE commercial context</span>}>{alerts.length ? <div className="card-list today-card-list">{alerts.map(alert => <article className="card today-card today-priority-card" key={alert.id}><div className="today-card-topline"><div className="row"><State value={alert.severity} /><State value={alert.type} /></div><small>{name(alert.account_id)}</small></div><div className="today-card-copy"><h3>{alert.trigger_reason}</h3><p>{alert.recommended_action}</p></div><div className="today-card-footer"><small>SAMPLE evidence IDs: {alert.evidence_ids.join(', ')}</small><div className="card-actions"><button onClick={() => onAccount(alert.account_id)}>Review Customer</button><button className="primary" onClick={() => onAction(alert)}>Create action</button></div></div></article>)}</div> : <Empty>No alertable commercial exceptions.</Empty>}</Panel><Panel title="Public intelligence" action={<span className="panel-kicker">Evidence inbox</span>}>{priority.length ? <div className="card-list today-card-list">{priority.map(signal => <article className="card today-card today-signal-card" key={signal.id}><div className="today-card-topline"><State value={signal.kind} /><SignalTruth signal={signal} /></div><div className="today-card-copy"><h3>{name(signal.account_id)} · {signal.title}</h3><p>{signal.relevance_explanation}</p></div><div className="today-card-footer"><small>{signal.observed_at ? `Observed ${new Date(signal.observed_at).toLocaleDateString('en-US', { timeZone: 'UTC' })} · ` : ''}Evidence: {signal.evidence_ids.join(', ')}</small><div className="card-actions">{!signal.source_url.includes('.invalid') && <a href={signal.source_url} target="_blank" rel="noreferrer">Evidence source ↗</a>}{signal.account_id && <button onClick={() => onAccount(signal.account_id!)}>Open Customer</button>}</div></div></article>)}</div> : <Empty>No governed intelligence is available.</Empty>}</Panel></div></div>
}
