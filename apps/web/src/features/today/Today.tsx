import { useEffect, useMemo, useState } from 'react'
import type { Account, Alert, CommandCenter, MonitorSignalBrief, OmniContext, Signal } from '../../types/api'
import { SignalBriefCard } from '../../components/SignalBriefCard'
import { curatedSignalBrief } from '../../components/signalBriefModel'
import { Button, Disclosure, Empty, Panel, State } from '../../components/UI'
import { CommercialRecoveryBriefing } from './CommercialRecoveryBriefing'
import './today.css'

export interface TodayFilters { kind: 'ALL' | 'PUBLIC_SIGNAL' | 'COMMERCIAL_REVIEW'; accountId: string; businessUnit: string }
const itemsById = <T extends { id: string }>(items: T[], ids?: string[]) => ids ? ids.flatMap(id => { const item = items.find(value => value.id === id); return item ? [item] : [] }) : items

export function Today({ commandCenter, state, alerts, signals, accounts, filters, onFilters, onAccount, onAction, onIntelligence, onMonitor, onEventSelect, onOmniContext }: { commandCenter?: CommandCenter; state: 'loading' | 'loaded' | 'unavailable'; alerts: Alert[]; signals: Signal[]; accounts: Account[]; filters: TodayFilters; onFilters: (filters: TodayFilters) => void; onAccount: (id: string) => void; onAction: (alert: Alert) => void; onIntelligence: () => void; onMonitor: () => void; onEventSelect: (id?: string) => void; onOmniContext: (context: Pick<OmniContext, 'selected_event_id' | 'selected_program_id' | 'active_filters' | 'visible_record_ids'>) => void }) {
  const [market, setMarket] = useState('')
  const [watchOpen, setWatchOpen] = useState(false)
  const [selectedEventId, setSelectedEventId] = useState<string>()
  const [selectedBriefContextId, setSelectedBriefContextId] = useState<string>()
  const [selectedEventAccountId, setSelectedEventAccountId] = useState<string>()
  const [selectedProgramId, setSelectedProgramId] = useState<string>()
  const [recoveryId, setRecoveryId] = useState(() => {
    const match = window.location.hash.match(/^#\/today\/brief\/([^/]+)$/)
    return match ? decodeURIComponent(match[1]) : ''
  })
  useEffect(() => {
    const changed = () => {
      const match = window.location.hash.match(/^#\/today\/brief\/([^/]+)$/)
      setRecoveryId(match ? decodeURIComponent(match[1]) : '')
    }
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const accountById = useMemo(() => new Map(accounts.map(account => [account.id, account])), [accounts])
  const current = useMemo(() => commandCenter?.current_signal_briefs ?? [], [commandCenter])
  const radar = useMemo(() => commandCenter?.upcoming_radar ?? [], [commandCenter])
  const selectedHub = commandCenter?.market_hubs.find(hub => hub.market === market)
  const visibleCurrent = useMemo(() => itemsById(current, selectedHub?.current_signal_ids), [current, selectedHub?.current_signal_ids])
  const visibleRadar = useMemo(() => itemsById(radar, selectedHub?.upcoming_signal_ids), [radar, selectedHub?.upcoming_signal_ids])
  const visibleAccounts = useMemo(() => market ? (commandCenter?.watched_accounts ?? []).filter(item => selectedHub?.watched_account_ids.includes(item.account_id)) : (commandCenter?.watched_accounts ?? []), [commandCenter?.watched_accounts, market, selectedHub?.watched_account_ids])
  const visiblePrograms = useMemo(() => market ? (commandCenter?.watched_programs ?? []).filter(item => selectedHub?.watched_program_ids.includes(item.program_id)) : (commandCenter?.watched_programs ?? []), [commandCenter?.watched_programs, market, selectedHub?.watched_program_ids])
  const alertById = useMemo(() => new Map(alerts.map(alert => [alert.id, alert])), [alerts])
  const allPriority = useMemo(() => commandCenter?.priority_briefing ?? [], [commandCenter])
  const priority = useMemo(() => allPriority.filter(item =>
    (filters.kind === 'ALL' || item.kind === filters.kind) &&
    (!filters.accountId || (item.signal_brief?.canonical_account_ids ?? [item.account_id]).includes(filters.accountId)) &&
    (!filters.businessUnit || item.business_unit_ids?.includes(filters.businessUnit))), [allPriority, filters])
  const businessUnits = useMemo(() => [...new Set(allPriority.flatMap(item => item.business_unit_ids ?? []))].sort(), [allPriority])
  const curatedIds = useMemo(() => commandCenter?.curated_reference_signal_ids ?? [], [commandCenter])
  const curatedSignals = useMemo(() => curatedIds.flatMap(id => { const signal = signals.find(item => item.id === id && item.data_mode === 'CURATED_PUBLIC'); return signal ? [signal] : [] }), [curatedIds, signals])
  const curated = useMemo(() => curatedSignals.map(signal => curatedSignalBrief(signal, accountById.get(signal.account_id ?? ''))), [accountById, curatedSignals])
  const missingCuratedCount = curatedIds.length - curated.length
  const visibleIds = useMemo(() => [...new Set([...priority.map(item => item.event_id ?? item.signal_brief?.id ?? item.id), ...(watchOpen ? [...visibleCurrent.map(item => item.id), ...visibleRadar.map(item => item.id), ...visibleAccounts.slice(0, 12).map(item => item.account_id), ...visiblePrograms.map(item => item.program_id), ...curated.map(item => item.id)] : [])])].slice(0, 50), [curated, priority, visibleAccounts, visibleCurrent, visiblePrograms, visibleRadar, watchOpen])
  useEffect(() => { onOmniContext({ selected_event_id: selectedEventId, selected_program_id: selectedProgramId, active_filters: { market, priority_kind: filters.kind, account_id: selectedEventAccountId ?? filters.accountId, business_unit_id: filters.businessUnit }, visible_record_ids: visibleIds }) }, [market, filters, onOmniContext, selectedEventAccountId, selectedEventId, selectedProgramId, visibleIds])
  useEffect(() => () => { onEventSelect(undefined); onOmniContext({}) }, [onEventSelect, onOmniContext])
  const name = (id: string) => accountById.get(id)?.name ?? accountById.get(id)?.legal_name ?? 'Unresolved Customer'
  const useBrief = (brief: MonitorSignalBrief) => { const contextId = brief.context_id ?? brief.id; const next = selectedBriefContextId === contextId ? undefined : brief.id; setSelectedBriefContextId(next ? contextId : undefined); setSelectedEventId(next); setSelectedEventAccountId(next ? brief.canonical_account_ids[0] : undefined); setSelectedProgramId(next ? brief.canonical_program_id : undefined); onEventSelect(next) }
  const changeFilters = (next: TodayFilters) => { setSelectedBriefContextId(undefined); setSelectedEventId(undefined); setSelectedEventAccountId(undefined); setSelectedProgramId(undefined); onEventSelect(undefined); onFilters(next) }
  const inspectPriority = (id: string) => {
    const target = document.getElementById(`priority-${id}`)
    target?.scrollIntoView({ block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
    target?.focus({ preventScroll: true })
  }
  const changeMarket = (nextMarket: string) => {
    const nextHub = commandCenter?.market_hubs.find(hub => hub.market === nextMarket)
    const nextVisibleEvents = new Set([...priority.map(item => item.event_id ?? item.signal_brief?.id ?? item.id), ...(nextHub ? nextHub.current_signal_ids : current.map(item => item.id)), ...(nextHub ? nextHub.upcoming_signal_ids : radar.map(item => item.id)), ...curated.map(item => item.id)])
    const nextVisiblePrograms = new Set(nextHub ? nextHub.watched_program_ids : (commandCenter?.watched_programs ?? []).map(item => item.program_id))
    if (selectedEventId && !nextVisibleEvents.has(selectedEventId)) { setSelectedBriefContextId(undefined); setSelectedEventId(undefined); setSelectedEventAccountId(undefined); onEventSelect(undefined) }
    if (selectedProgramId && !nextVisiblePrograms.has(selectedProgramId)) setSelectedProgramId(undefined)
    setMarket(nextMarket)
  }
  const recoveryItem = allPriority.find(item => item.id === recoveryId && item.kind === 'COMMERCIAL_REVIEW')
  if (recoveryItem) return <div className="surface today-surface"><CommercialRecoveryBriefing key={recoveryItem.id} item={recoveryItem} alert={alertById.get(recoveryItem.id)} onBack={() => { setRecoveryId(''); window.location.hash = '/today' }} onAccount={onAccount} onAction={onAction} /></div>
  return <div className="surface today-surface">
    <header className="page-title today-title"><h1>Today</h1><p>Your next commercial decisions</p></header>
    {state === 'loading' && <p role="status">Refreshing your briefing…</p>}
    {state === 'unavailable' ? <Panel title="Today briefing unavailable"><Empty>Today briefing is unavailable. This is not zero activity. Retry using the workspace notice above; your filters are retained.</Empty></Panel> : <>
    <section className="today-priority-summary" aria-label="Top priorities">
      {priority.slice(0, 3).map(item => <article key={item.id} className="today-priority-card" data-summary-id={item.id}>
        <div className="today-item-heading"><span className="eyebrow">{item.kind === 'PUBLIC_SIGNAL' ? (item.lifecycle_state === 'SAVED_RECENT' ? 'Saved public intelligence' : 'Public intelligence') : 'Internal intelligence'}</span>{item.severity && <State value={item.severity} />}</div>
        <h2>{item.account_id ? name(item.account_id) : 'Prospect research'}: {item.signal_brief?.headline ?? item.reason}</h2>
        <p>{item.signal_brief?.what_happened ?? item.reason}</p>
        <p className="today-card-next">{item.recommended_action ?? 'Review supporting evidence before choosing an action.'}</p>
        <Button variant="primary" onClick={() => inspectPriority(item.id)}>Review priority <span aria-hidden="true">→</span></Button>
      </article>)}
    </section>
    <div className="today-priority-toolbar">
      <div className="today-priority-tabs" role="group" aria-label="Priority source">
        {([['ALL', 'All priorities'], ['PUBLIC_SIGNAL', 'Public intelligence'], ['COMMERCIAL_REVIEW', 'Internal intelligence']] as const).map(([kind, label]) => <button key={kind} type="button" aria-pressed={filters.kind === kind} onClick={() => changeFilters({ ...filters, kind })}>{label}</button>)}
      </div>
      <label>Customer / prospect<select aria-label="Filter priorities by customer or prospect" value={filters.accountId} onChange={event => changeFilters({ ...filters, accountId: event.target.value })}><option value="">All (Customers &amp; Prospects)</option>{accounts.map(account => <option key={account.id} value={account.id}>{account.name ?? account.legal_name}</option>)}</select></label>
      <label>Business unit<select aria-label="Filter priorities by business unit" value={filters.businessUnit} onChange={event => changeFilters({ ...filters, businessUnit: event.target.value })}><option value="">All business units</option>{businessUnits.map(unit => <option key={unit} value={unit}>{unit.replaceAll('-', ' ')}</option>)}</select></label>
    </div>
    <div className="today-command-grid">
      <Panel title="What changed / needs attention" action={<span className="panel-kicker">{priority.length} priorities</span>}>
        {priority.length ? <ol className="today-attention-list">{priority.map((item, index) =>
          <li className="today-attention-item" key={item.id} id={`priority-${item.id}`} tabIndex={-1} data-priority-id={item.id}>
            <span className="today-rank" aria-label={`Priority ${index + 1}`}>{index + 1}</span>
            <div className="today-item-heading"><button className="today-customer-link" disabled={!item.account_id} onClick={() => item.account_id && onAccount(item.account_id)}>{item.account_id ? name(item.account_id) : 'Prospect research'}</button><small>{item.kind === 'PUBLIC_SIGNAL' ? (item.lifecycle_state === 'SAVED_RECENT' ? 'Saved public intelligence · revalidate' : 'Public intelligence') : 'Internal intelligence'}</small>{item.observed_at && <time dateTime={item.observed_at}>{new Date(item.observed_at).toLocaleDateString('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' })}</time>}</div>
            <div className="today-priority-meaning"><h3>{item.signal_brief?.headline ?? item.reason}</h3><p><strong>Why:</strong> {item.reason}</p><p><strong>Next:</strong> {item.recommended_action ?? 'Review evidence before choosing the next action.'}</p>
              <Disclosure title="Evidence and governed action">
                {item.signal_brief ? <SignalBriefCard brief={item.signal_brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} selected={selectedBriefContextId === (item.signal_brief.context_id ?? item.signal_brief.id)} /> : <><p className="today-evidence-note">BTX commercial record · Evidence IDs: {item.evidence_ids.length ? item.evidence_ids.join(', ') : 'Unavailable'}</p><div className="card-actions"><Button variant="primary" onClick={() => { setRecoveryId(item.id); window.location.hash = `/today/brief/${encodeURIComponent(item.id)}` }}>Open recovery briefing</Button>{item.account_id && <Button onClick={() => onAccount(item.account_id!)}>Review Customer</Button>}{alertById.get(item.id) && <Button variant="ghost" onClick={() => onAction(alertById.get(item.id)!)}>Create action</Button>}</div></>}
              </Disclosure>
            </div>
            {item.severity && <State value={item.severity} />}
          </li>)}</ol> : <Empty>No priorities match this scope. Change the filters to review other work.</Empty>}
      </Panel>
    </div>
    <Disclosure title="Market watch and source coverage" open={watchOpen} onOpenChange={open => { setWatchOpen(open); if (!open && !priority.some(item => (item.event_id ?? item.signal_brief?.id ?? item.id) === selectedEventId)) { setSelectedBriefContextId(undefined); setSelectedEventId(undefined); setSelectedEventAccountId(undefined); setSelectedProgramId(undefined); onEventSelect(undefined) } }}>
    <Panel title="Current public intelligence" action={<Button variant="ghost" onClick={onMonitor}>Source health</Button>}>{visibleCurrent.length ? <div className="seller-signal-list">{visibleCurrent.map(brief => <SignalBriefCard key={brief.context_id ?? brief.id} brief={brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} />)}</div> : <Empty>No current public signal is eligible{market ? ` for ${market}` : ''}.</Empty>}</Panel>
    <Panel title="Upcoming Radar" action={<span className="panel-kicker">Only source-supported future dates</span>}>{visibleRadar.length ? <div className="seller-signal-list radar-list">{visibleRadar.map(brief => <SignalBriefCard key={brief.context_id ?? brief.id} brief={brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} />)}</div> : <Empty>No governed upcoming dates{market ? ` for ${market}` : ''}. Unknown dates are not promoted into Radar.</Empty>}</Panel>
    <section className="today-market-section" aria-labelledby="market-hubs-title"><div><span className="eyebrow">Navigation and context</span><h2 id="market-hubs-title">Market Hubs</h2></div><nav className="today-market-hubs" aria-label="Market hubs"><Button variant={market ? 'ghost' : 'primary'} aria-pressed={!market} onClick={() => changeMarket('')}>All markets</Button>{(commandCenter?.market_hubs ?? []).map(hub => <Button key={hub.market} variant={market === hub.market ? 'primary' : 'ghost'} aria-pressed={market === hub.market} onClick={() => changeMarket(hub.market)}>{hub.market}<span>{hub.current_signal_ids.length + hub.upcoming_signal_ids.length}</span></Button>)}</nav></section>
    <div className="today-watch-grid">
      <Panel title="Recommended Customer watchlist" action={<span className="panel-kicker">System recommended · read only</span>}>{visibleAccounts.length ? <div className="today-watch-list">{visibleAccounts.slice(0, 12).map(item => <button key={item.account_id} onClick={() => onAccount(item.account_id)}><span><strong>{item.name}</strong><small>{item.markets.join(' · ')}</small></span><State value={item.relationship === 'TARGET' ? 'PROSPECT' : 'CUSTOMER'} /></button>)}</div> : <Empty>No governed watch targets{market ? ` for ${market}` : ''}. No user saves are implied.</Empty>}</Panel>
      <Panel title="Watched programs" action={<span className="panel-kicker">Governed Signal Brief associations</span>}>{visiblePrograms.length ? <div className="today-watch-list">{visiblePrograms.map(item => <button key={item.program_id} aria-pressed={selectedProgramId === item.program_id} onClick={() => setSelectedProgramId(selectedProgramId === item.program_id ? undefined : item.program_id)}><span><strong>{item.name}</strong><small>{item.reason}</small></span></button>)}</div> : <Empty>No current or upcoming Signal Brief has a canonical program association{market ? ` for ${market}` : ''}.</Empty>}</Panel>
    </div>
    <Panel title={market ? `${market} coverage and gaps` : 'Coverage and source freshness'} action={<Button variant="ghost" onClick={onMonitor}>Open Monitor</Button>}><p className="truth-note">{commandCenter?.daily_briefing.live_intelligence_available ? 'Current eligible collected evidence is available.' : 'No current eligible live intelligence is available.'} Worker readiness does not prove that a schedule is active.</p>{selectedHub && <div className="today-hub-summary"><p><strong>Source coverage:</strong> {selectedHub.source_coverage.length ? selectedHub.source_coverage.map(source => `${source.source_name} (${source.state.replaceAll('_', ' ').toLocaleLowerCase()})`).join(' · ') : 'No declared source coverage'}</p>{selectedHub.gaps.length ? <ul>{selectedHub.gaps.map(gap => <li key={gap}>{gap}</li>)}</ul> : <p>No governed coverage gap is reported for this market.</p>}</div>}{!selectedHub && (commandCenter?.source_health_warnings.length ?? 0) > 0 && <Disclosure title={`${commandCenter!.source_health_warnings.length} source coverage notices`}><ul>{commandCenter!.source_health_warnings.map(item => <li key={item.source_id}><strong>{item.source_name}</strong>: {item.message}</li>)}</ul></Disclosure>}{!selectedHub && (commandCenter?.missingness.length ?? 0) > 0 && <p className="muted">{commandCenter!.missingness.join(' ')}</p>}</Panel>
    <Panel title="Public intelligence" action={<Button variant="ghost" onClick={onIntelligence}>View Intelligence</Button>}><p className="monitor-intro">Stored public scenarios demonstrate evidence workflows. They are curated public material, not today’s live collection.</p>{curated.length ? <div className="seller-signal-list curated-reference-list">{curated.map(brief => <SignalBriefCard key={brief.context_id ?? brief.id} brief={brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} selected={selectedBriefContextId === (brief.context_id ?? brief.id)} />)}</div> : <Empty>No projected curated public evidence is available.</Empty>}{missingCuratedCount > 0 && <p className="muted">{missingCuratedCount} projected curated record{missingCuratedCount === 1 ? '' : 's'} could not be resolved from the current Intelligence payload; no substitute was shown.</p>}</Panel>
    </Disclosure>
    </>}
  </div>
}
