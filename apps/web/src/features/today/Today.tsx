import { FilterBar, type AppliedFilter } from '../../components/FilterBar'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Account, Alert, CommandCenter, CommandPriorityItem, MonitorSignalBrief, OmniAssessmentSelection, OmniContext, Signal } from '../../types/api'
import { SignalBriefCard } from '../../components/SignalBriefCard'
import { curatedSignalBrief } from '../../components/signalBriefModel'
import { Button, Disclosure, Empty, Panel, State } from '../../components/UI'
import { HighCardinalitySelector } from '../../components/HighCardinalitySelector'
import { WorklistPagination } from '../../components/WorklistPagination'
import { clampPage, pageSlice } from '../../components/worklistModel'
import { CommercialRecoveryBriefing } from './CommercialRecoveryBriefing'
import type { WorkspaceLocation } from '../../app/navigation'
import './today.css'

export interface TodayFilters { kind: 'ALL' | 'PUBLIC_SIGNAL' | 'COMMERCIAL_REVIEW'; accountId: string; businessUnit: string; query: string; sort: 'RANKED' | 'RECENT' | 'OLDEST' | 'CUSTOMER_ASC' | 'CUSTOMER_DESC'; page: number; validationPage: number }
const itemsById = <T extends { id: string }>(items: T[], ids?: string[]) => ids ? ids.flatMap(id => { const item = items.find(value => value.id === id); return item ? [item] : [] }) : items
const matchesScope = (item: CommandPriorityItem, filters: TodayFilters) =>
  (filters.kind === 'ALL' || item.kind === filters.kind) &&
  (!filters.accountId || (item.signal_brief?.canonical_account_ids ?? [item.account_id]).includes(filters.accountId)) &&
  (!filters.businessUnit || item.business_unit_ids?.includes(filters.businessUnit))
const dateLabel = (value?: string) => value ? new Date(value).toLocaleDateString('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' }) : undefined
const PAGE_SIZE = 10
const stableId = (item: CommandPriorityItem) => item.id
const missingLastDate = (left: CommandPriorityItem, right: CommandPriorityItem, direction: 1 | -1) => {
  if (!left.observed_at || !right.observed_at) return left.observed_at ? -1 : right.observed_at ? 1 : stableId(left).localeCompare(stableId(right))
  return direction * left.observed_at.localeCompare(right.observed_at) || stableId(left).localeCompare(stableId(right))
}

export function Today({ commandCenter, state, alerts, signals, accounts, filters, onFilters, onAccount, onAction, onIntelligence, onSourceHealth, onEventSelect, onOmniContext, location, onLocationChange }: { commandCenter?: CommandCenter; state: 'loading' | 'loaded' | 'unavailable'; alerts: Alert[]; signals: Signal[]; accounts: Account[]; filters: TodayFilters; onFilters: (filters: TodayFilters) => void; onAccount: (id: string, assessment?: OmniAssessmentSelection) => void; onAction: (alert: Alert) => void; onIntelligence: () => void; onSourceHealth?: () => void; onEventSelect: (id?: string) => void; onOmniContext: (context: Pick<OmniContext, 'selected_event_id' | 'selected_assessment' | 'selected_program_id' | 'active_filters' | 'visible_record_ids'>) => void; location: WorkspaceLocation; onLocationChange: (next: WorkspaceLocation, mode?: 'push' | 'replace') => void }) {
  const market = String(location.filters?.market ?? '')
  const [watchOpen, setWatchOpen] = useState(false)
  const [selectedEventId, setSelectedEventId] = useState<string | undefined>(location.eventId)
  const [selectedAssessment, setSelectedAssessment] = useState<OmniAssessmentSelection | undefined>(() => location.assessment ? { assessment_id: location.assessment.assessmentId, assessment_version: location.assessment.assessmentVersion, event_id: location.assessment.eventId, account_id: location.assessment.accountId } : undefined)
  const [selectedBriefContextId, setSelectedBriefContextId] = useState<string | undefined>(location.recordId ?? location.assessment?.assessmentId)
  const [selectedEventAccountId, setSelectedEventAccountId] = useState<string | undefined>(location.assessment?.accountId)
  const [selectedProgramId, setSelectedProgramId] = useState<string>()
  const recoveryId = location.subview === 'recovery' ? location.recordId ?? '' : ''
  const accountById = useMemo(() => new Map(accounts.map(account => [account.id, account])), [accounts])
  const current = useMemo(() => commandCenter?.current_signal_briefs ?? [], [commandCenter])
  const radar = useMemo(() => commandCenter?.upcoming_radar ?? [], [commandCenter])
  const selectedHub = commandCenter?.market_hubs.find(hub => hub.market === market)
  const visibleCurrent = useMemo(() => itemsById(current, selectedHub?.current_signal_ids), [current, selectedHub?.current_signal_ids])
  const visibleRadar = useMemo(() => itemsById(radar, selectedHub?.upcoming_signal_ids), [radar, selectedHub?.upcoming_signal_ids])
  const visibleAccounts = useMemo(() => market ? (commandCenter?.watched_accounts ?? []).filter(item => selectedHub?.watched_account_ids.includes(item.account_id)) : (commandCenter?.watched_accounts ?? []), [commandCenter?.watched_accounts, market, selectedHub?.watched_account_ids])
  const visiblePrograms = useMemo(() => market ? (commandCenter?.watched_programs ?? []).filter(item => selectedHub?.watched_program_ids.includes(item.program_id)) : (commandCenter?.watched_programs ?? []), [commandCenter?.watched_programs, market, selectedHub?.watched_program_ids])
  const alertById = useMemo(() => new Map(alerts.map(alert => [alert.id, alert])), [alerts])
  const name = useCallback((id: string) => accountById.get(id)?.name ?? accountById.get(id)?.legal_name ?? 'Unresolved Customer', [accountById])
  const allPriority = useMemo(() => commandCenter?.priority_briefing ?? [], [commandCenter])
  const allValidation = useMemo(() => commandCenter?.needs_validation_assessments ?? [], [commandCenter])
  const queryMatch = useCallback((item: CommandPriorityItem) => !filters.query.trim() || `${item.account_id ? accountById.get(item.account_id)?.name ?? accountById.get(item.account_id)?.legal_name ?? '' : ''} ${item.reason} ${item.recommended_action ?? ''} ${item.signal_brief?.headline ?? ''}`.toLocaleLowerCase().includes(filters.query.trim().toLocaleLowerCase()), [accountById, filters.query])
  const priority = useMemo(() => allPriority.filter(item => matchesScope(item, filters) && queryMatch(item)), [allPriority, filters, queryMatch])
  const validation = useMemo(() => filters.kind === 'COMMERCIAL_REVIEW' ? [] : allValidation.filter(item => matchesScope(item, filters) && queryMatch(item)), [allValidation, filters, queryMatch])
  const sortedPriority = useMemo(() => priority.map((item, rank) => ({ item, rank })).sort((left, right) => {
    if (filters.sort === 'RANKED') return left.rank - right.rank
    if (filters.sort === 'RECENT') return missingLastDate(left.item, right.item, -1)
    if (filters.sort === 'OLDEST') return missingLastDate(left.item, right.item, 1)
    const comparison = name(left.item.account_id ?? '').localeCompare(name(right.item.account_id ?? ''))
    return (filters.sort === 'CUSTOMER_DESC' ? -comparison : comparison) || left.rank - right.rank || stableId(left.item).localeCompare(stableId(right.item))
  }).map(value => value.item), [priority, filters.sort, name])
  const priorityPage = clampPage(filters.page, sortedPriority.length, PAGE_SIZE)
  const validationPage = clampPage(filters.validationPage, validation.length, PAGE_SIZE)
  const displayedPriority = useMemo(() => pageSlice(sortedPriority, priorityPage, PAGE_SIZE), [sortedPriority, priorityPage])
  const displayedValidation = useMemo(() => pageSlice(validation, validationPage, PAGE_SIZE), [validation, validationPage])
  const businessUnits = useMemo(() => [...new Set([...allPriority, ...allValidation].flatMap(item => item.business_unit_ids ?? []))].sort(), [allPriority, allValidation])
  const curatedIds = useMemo(() => commandCenter?.curated_reference_signal_ids ?? [], [commandCenter])
  const curatedSignals = useMemo(() => curatedIds.flatMap(id => { const signal = signals.find(item => item.id === id && item.data_mode === 'CURATED_PUBLIC'); return signal ? [signal] : [] }), [curatedIds, signals])
  const curated = useMemo(() => curatedSignals.map(signal => curatedSignalBrief(signal, accountById.get(signal.account_id ?? ''))), [accountById, curatedSignals])
  const missingCuratedCount = curatedIds.length - curated.length
  const visibleIds = useMemo(() => [...new Set([...priority.map(item => item.event_id ?? item.signal_brief?.id ?? item.id), ...validation.map(item => item.event_id ?? item.signal_brief?.id ?? item.id), ...(watchOpen ? [...visibleCurrent.map(item => item.id), ...visibleRadar.map(item => item.id), ...visibleAccounts.slice(0, 12).map(item => item.account_id), ...visiblePrograms.map(item => item.program_id), ...curated.map(item => item.id)] : [])])].slice(0, 50), [curated, priority, validation, visibleAccounts, visibleCurrent, visiblePrograms, visibleRadar, watchOpen])
  useEffect(() => { onOmniContext({ selected_event_id: selectedEventId, selected_assessment: selectedAssessment, selected_program_id: selectedProgramId, active_filters: { market, priority_kind: filters.kind, account_id: selectedEventAccountId ?? filters.accountId, business_unit_id: filters.businessUnit }, visible_record_ids: visibleIds }) }, [market, filters, onOmniContext, selectedAssessment, selectedEventAccountId, selectedEventId, selectedProgramId, visibleIds])
  useEffect(() => () => { onEventSelect(undefined); onOmniContext({}) }, [onEventSelect, onOmniContext])
  const locationFor = (next: TodayFilters, recordId = location.recordId) => ({ surface: 'today' as const, recordId, eventId: location.eventId, assessment: location.assessment, anchor: location.anchor, filters: { ...(market ? { market } : {}), ...(next.kind !== 'ALL' ? { kind: next.kind } : {}), ...(next.accountId ? { account: next.accountId } : {}), ...(next.businessUnit ? { business_unit: next.businessUnit } : {}), ...(next.query ? { query: next.query } : {}), ...(next.page > 1 ? { page: String(next.page) } : {}), ...(next.validationPage > 1 ? { validation_page: String(next.validationPage) } : {}) }, ...(next.sort !== 'RANKED' ? { sort: next.sort } : {}) })
  const useBrief = (brief: MonitorSignalBrief) => { const selectionKey = brief.assessment_id ?? brief.context_id ?? brief.id; const next = selectedBriefContextId === selectionKey ? undefined : brief.id; const accountId = brief.canonical_account_ids[0]; const assessment = next && brief.assessment_id && brief.assessment_version && accountId ? { assessment_id: brief.assessment_id, assessment_version: brief.assessment_version, event_id: brief.id, account_id: accountId } : undefined; setSelectedBriefContextId(next ? selectionKey : undefined); setSelectedEventId(next); setSelectedAssessment(assessment); setSelectedEventAccountId(next ? accountId : undefined); setSelectedProgramId(next ? brief.canonical_program_id : undefined); onEventSelect(next); onLocationChange({ ...locationFor(filters, next ? selectionKey : undefined), eventId: next, assessment: assessment ? { assessmentId: assessment.assessment_id, assessmentVersion: assessment.assessment_version, eventId: assessment.event_id, accountId: assessment.account_id } : undefined, anchor: next ? `priority-${brief.id}` : undefined }, 'replace') }
  const changeFilters = (next: TodayFilters) => { setSelectedBriefContextId(undefined); setSelectedEventId(undefined); setSelectedAssessment(undefined); setSelectedEventAccountId(undefined); setSelectedProgramId(undefined); onEventSelect(undefined); onFilters(next); onLocationChange(locationFor(next, undefined), 'replace') }
  const inspectPriority = (id: string) => {
    const target = document.getElementById(`priority-${id}`)
    target?.scrollIntoView({ block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
    target?.focus({ preventScroll: true }); onLocationChange(locationFor(filters, id), 'replace')
  }
  const changeMarket = (nextMarket: string) => {
    const nextHub = commandCenter?.market_hubs.find(hub => hub.market === nextMarket)
    const nextVisibleEvents = new Set([...priority.map(item => item.event_id ?? item.signal_brief?.id ?? item.id), ...validation.map(item => item.event_id ?? item.signal_brief?.id ?? item.id), ...(nextHub ? nextHub.current_signal_ids : current.map(item => item.id)), ...(nextHub ? nextHub.upcoming_signal_ids : radar.map(item => item.id)), ...curated.map(item => item.id)])
    const nextVisiblePrograms = new Set(nextHub ? nextHub.watched_program_ids : (commandCenter?.watched_programs ?? []).map(item => item.program_id))
    if (selectedEventId && !nextVisibleEvents.has(selectedEventId)) { setSelectedBriefContextId(undefined); setSelectedEventId(undefined); setSelectedAssessment(undefined); setSelectedEventAccountId(undefined); onEventSelect(undefined) }
    if (selectedProgramId && !nextVisiblePrograms.has(selectedProgramId)) setSelectedProgramId(undefined)
    onLocationChange({ ...location, filters: { ...location.filters, market: nextMarket } }, 'replace')
  }
  const clearFilters = () => changeFilters({ ...filters, query: '', kind: 'ALL', accountId: '', businessUnit: '', page: 1, validationPage: 1 })
  const applied: AppliedFilter[] = [
    ...(filters.query ? [{ key: 'query', label: `Search: ${filters.query}`, remove: () => changeFilters({ ...filters, query: '' }) }] : []),
    ...(filters.kind !== 'ALL' ? [{ key: 'kind', label: `Source: ${filters.kind}`, remove: () => changeFilters({ ...filters, kind: 'ALL' }) }] : []),
    ...(filters.accountId ? [{ key: 'account', label: `Customer: ${name(filters.accountId)}`, remove: () => changeFilters({ ...filters, accountId: '' }) }] : []),
    ...(filters.businessUnit ? [{ key: 'bu', label: `Business unit: ${filters.businessUnit}`, remove: () => changeFilters({ ...filters, businessUnit: '' }) }] : []),
  ]
  const recoveryItem = allPriority.find(item => item.id === recoveryId && item.kind === 'COMMERCIAL_REVIEW')
  if (recoveryItem) return <div className="surface today-surface"><CommercialRecoveryBriefing key={recoveryItem.id} item={recoveryItem} alert={alertById.get(recoveryItem.id)} onBack={() => onLocationChange({ ...location, subview: undefined, recordId: undefined }, 'push')} onAccount={onAccount} onAction={onAction} /></div>
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
    <FilterBar label="Today filters" search={<label className="today-search">Search priorities<input type="search" aria-label="Search Today work" value={filters.query} onChange={event => changeFilters({ ...filters, query: event.target.value, page: 1, validationPage: 1 })} /></label>} sort={<label>Worklist order<select aria-label="Sort Today worklist" value={filters.sort} onChange={event => changeFilters({ ...filters, sort: event.target.value as TodayFilters['sort'], page: 1 })}><option value="RANKED">Ranked decision order</option><option value="RECENT">Most recent first</option><option value="OLDEST">Oldest first</option><option value="CUSTOMER_ASC">Customer A–Z</option><option value="CUSTOMER_DESC">Customer Z–A</option></select></label>} filters={applied} onClear={clearFilters} count={priority.length + validation.length}>
      <label>Priority source<select aria-label="Priority source" value={filters.kind} onChange={event => changeFilters({ ...filters, kind: event.target.value as TodayFilters['kind'], page: 1, validationPage: 1 })}><option value="ALL">All priorities</option><option value="PUBLIC_SIGNAL">Public intelligence</option><option value="COMMERCIAL_REVIEW">Internal intelligence</option></select></label>
      <HighCardinalitySelector label="Filter priorities by customer or prospect" value={filters.accountId} onChange={accountId => changeFilters({ ...filters, accountId, page: 1, validationPage: 1 })} allChoice={{ label: 'All customers and prospects', description: 'Search the complete eligible Today scope' }} choices={accounts.map(account => ({ id: account.id, label: account.name ?? account.legal_name ?? 'Unnamed organization', description: [account.relationship === 'CURRENT_CUSTOMER' ? 'Customer' : account.relationship === 'PROSPECT' || account.relationship === 'TARGET' ? 'Prospect' : 'Classification unavailable', account.location?.state].filter(Boolean).join(' · '), searchText: [account.legal_name, account.domain, ...(account.industries ?? [])].filter(Boolean).join(' ') }))} recentIds={[...priority, ...validation].flatMap(item => item.account_id ? [item.account_id] : [])} />
      <label>Business unit<select aria-label="Filter priorities by business unit" value={filters.businessUnit} onChange={event => changeFilters({ ...filters, businessUnit: event.target.value })}><option value="">All business units</option>{businessUnits.map(unit => <option key={unit} value={unit}>{unit.replaceAll('-', ' ')}</option>)}</select></label>
    </FilterBar>
    <p className="today-lane-summary" role="status">{allPriority.length} total action priorities · {priority.length} filtered · {displayedPriority.length} displayed · {allValidation.length} total needs validation · {validation.length} filtered</p>
    <div className="today-command-grid">
      <Panel title="Action priorities" action={<span className="panel-kicker">{priority.length} confirmed for action</span>}>
        {priority.length ? <><ol className="today-attention-list">{displayedPriority.map((item) => {
          const index = priority.indexOf(item)
          const familyCount = priority.filter(candidate => candidate.account_id === item.account_id && candidate.recommended_action === item.recommended_action).length
          return (
          <li className="today-attention-item" key={item.id} id={`priority-${item.id}`} tabIndex={-1} data-priority-id={item.id}>
            <span className="today-rank" aria-label={`Priority ${index + 1}`}>{index + 1}</span>
            <div className="today-item-heading"><button className="today-customer-link" disabled={!item.account_id} onClick={() => item.account_id && onAccount(item.account_id)}>{item.account_id ? name(item.account_id) : 'Prospect research'}</button><small>{item.kind === 'PUBLIC_SIGNAL' ? (item.lifecycle_state === 'SAVED_RECENT' ? 'Saved public intelligence · revalidate' : 'Public intelligence') : 'Internal intelligence'}{familyCount > 1 ? ` · ${familyCount} related recommendations` : ''}</small>{item.observed_at && <time dateTime={item.observed_at}>{dateLabel(item.observed_at)}</time>}</div>
            <div className="today-priority-meaning"><h3>{item.signal_brief?.headline ?? item.reason}</h3><p><strong>Why:</strong> {item.reason}</p><p><strong>Next:</strong> {item.recommended_action ?? 'Review evidence before choosing the next action.'}</p>
              <Disclosure title="Evidence and governed action">
                {item.signal_brief ? <SignalBriefCard brief={item.signal_brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} selected={selectedBriefContextId === (item.signal_brief.assessment_id ?? item.signal_brief.context_id ?? item.signal_brief.id)} /> : <><p className="today-evidence-note">BTX commercial record · Evidence IDs: {item.evidence_ids.length ? item.evidence_ids.join(', ') : 'Unavailable'}</p><div className="card-actions"><Button variant="primary" onClick={() => onLocationChange({ ...location, subview: 'recovery', recordId: item.id, anchor: `priority-${item.id}` }, 'push')}>Open recovery briefing</Button>{item.account_id && <Button onClick={() => onAccount(item.account_id!)}>Review Customer</Button>}{alertById.get(item.id) && <Button variant="ghost" onClick={() => onAction(alertById.get(item.id)!)}>Create action</Button>}</div></>}
              </Disclosure>
            </div>
            {item.severity && <State value={item.severity} />}
          </li> )})}</ol><WorklistPagination page={priorityPage} pageSize={PAGE_SIZE} total={priority.length} onPage={page => changeFilters({ ...filters, page })} /></> : <Empty>{allPriority.length ? 'No action priorities match the current search and filters. The complete eligible queue is unchanged.' : validation.length ? 'No eligible action priorities exist. Review the separate validation lane below.' : 'No eligible action priorities exist for this briefing.'}<Button onClick={clearFilters}>Clear filters</Button></Empty>}
      </Panel>
      {filters.kind !== 'COMMERCIAL_REVIEW' && <Panel title="Needs validation" action={<span className="panel-kicker">{validation.length} to review</span>}>
        {validation.length ? <><div className="today-validation-list">{displayedValidation.map(item => {
          const brief = item.signal_brief
          const score = brief?.signal_confidence?.score
          return <article className="today-validation-item" key={item.id} data-validation-id={item.id}>
            <div className="today-validation-head"><div><span className="today-validation-label">Needs validation</span><button className="today-customer-link" disabled={!item.account_id} onClick={() => item.account_id && onAccount(item.account_id)}>{item.account_id ? name(item.account_id) : 'Prospect research'}</button></div>{item.observed_at && <time dateTime={item.observed_at}>{dateLabel(item.observed_at)}</time>}</div>
            <h3>{brief?.headline ?? item.reason}</h3>
            <div className="today-validation-facts"><span><strong>Signal Confidence</strong> {score == null ? 'More evidence needed' : `${score}/100`}</span><span>Potential BTX relevance not yet established</span></div>
            <p><strong>Next:</strong> {item.recommended_action ?? 'Validate the account-specific evidence before choosing an action.'}</p>
            {brief && <Disclosure title="Evidence, component hierarchy, and uncertainty"><SignalBriefCard brief={brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} selected={selectedBriefContextId === (brief.assessment_id ?? brief.context_id ?? brief.id)} /></Disclosure>}
          </article>
        })}</div><WorklistPagination page={validationPage} pageSize={PAGE_SIZE} total={validation.length} onPage={page => changeFilters({ ...filters, validationPage: page })} /></> : <Empty>{allValidation.length ? 'No validation assessments match the current search and filters. The complete validation lane is unchanged.' : 'No eligible public intelligence currently needs validation.'}</Empty>}
      </Panel>
      }
    </div>
    <Disclosure title="Market watch and source coverage" open={watchOpen} onOpenChange={open => { setWatchOpen(open); if (!open && ![...priority, ...validation].some(item => (item.event_id ?? item.signal_brief?.id ?? item.id) === selectedEventId)) { setSelectedBriefContextId(undefined); setSelectedEventId(undefined); setSelectedAssessment(undefined); setSelectedEventAccountId(undefined); setSelectedProgramId(undefined); onEventSelect(undefined) } }}>
    <Panel title="Current public intelligence" action={<Button variant="ghost" onClick={onSourceHealth ?? onIntelligence}>{onSourceHealth ? 'Source Health' : 'View Intelligence'}</Button>}>{visibleCurrent.length ? <div className="seller-signal-list">{visibleCurrent.map(brief => <SignalBriefCard key={brief.context_id ?? brief.id} brief={brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} />)}</div> : <Empty>No current public signal is eligible{market ? ` for ${market}` : ''}.</Empty>}</Panel>
    <Panel title="Upcoming Radar" action={<span className="panel-kicker">Only source-supported future dates</span>}>{visibleRadar.length ? <div className="seller-signal-list radar-list">{visibleRadar.map(brief => <SignalBriefCard key={brief.context_id ?? brief.id} brief={brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} />)}</div> : <Empty>No governed upcoming dates{market ? ` for ${market}` : ''}. Unknown dates are not promoted into Radar.</Empty>}</Panel>
    <section className="today-market-section" aria-labelledby="market-hubs-title"><h2 id="market-hubs-title">Market Hubs</h2><FilterBar label="Market watch filters" search={null} filters={market ? [{ key: 'market', label: `Market: ${market}`, remove: () => changeMarket('') }] : []} onClear={() => changeMarket('')} count={visibleCurrent.length + visibleRadar.length}><label>Watch market<select aria-label="Watch market" value={market} onChange={event => changeMarket(event.target.value)}><option value="">All markets</option>{(commandCenter?.market_hubs ?? []).map(hub => <option key={hub.market}>{hub.market}</option>)}</select></label></FilterBar></section>
    <div className="today-watch-grid">
      <Panel title="Recommended Customer watchlist" action={<span className="panel-kicker">System recommended · read only</span>}>{visibleAccounts.length ? <div className="today-watch-list">{visibleAccounts.slice(0, 12).map(item => <button key={item.account_id} onClick={() => onAccount(item.account_id)}><span><strong>{item.name}</strong><small>{item.markets.join(' · ')}</small></span><State value={item.relationship === 'TARGET' ? 'PROSPECT' : 'CUSTOMER'} /></button>)}</div> : <Empty>No governed watch targets{market ? ` for ${market}` : ''}. No user saves are implied.</Empty>}</Panel>
      <Panel title="Watched programs" action={<span className="panel-kicker">Governed Signal Brief associations</span>}>{visiblePrograms.length ? <div className="today-watch-list">{visiblePrograms.map(item => <button key={item.program_id} aria-pressed={selectedProgramId === item.program_id} onClick={() => setSelectedProgramId(selectedProgramId === item.program_id ? undefined : item.program_id)}><span><strong>{item.name}</strong><small>{item.reason}</small></span></button>)}</div> : <Empty>No current or upcoming Signal Brief has a canonical program association{market ? ` for ${market}` : ''}.</Empty>}</Panel>
    </div>
    <Panel title={market ? `${market} coverage and gaps` : 'Coverage and source freshness'} action={<Button variant="ghost" onClick={onSourceHealth ?? onIntelligence}>{onSourceHealth ? 'Open Source Health' : 'View Intelligence'}</Button>}><p className="truth-note">{commandCenter?.daily_briefing.live_intelligence_available ? 'Current eligible collected evidence is available.' : 'No current eligible live intelligence is available.'} Worker readiness does not prove that a schedule is active.</p>{selectedHub && <div className="today-hub-summary"><p><strong>Source coverage:</strong> {selectedHub.source_coverage.length ? selectedHub.source_coverage.map(source => `${source.source_name} (${source.state.replaceAll('_', ' ').toLocaleLowerCase()})`).join(' · ') : 'No declared source coverage'}</p>{selectedHub.gaps.length ? <ul>{selectedHub.gaps.map(gap => <li key={gap}>{gap}</li>)}</ul> : <p>No governed coverage gap is reported for this market.</p>}</div>}{!selectedHub && (commandCenter?.source_health_warnings.length ?? 0) > 0 && <Disclosure title={`${commandCenter!.source_health_warnings.length} source coverage notices`}><ul>{commandCenter!.source_health_warnings.map(item => <li key={item.source_id}><strong>{item.source_name}</strong>: {item.message}</li>)}</ul></Disclosure>}{!selectedHub && (commandCenter?.missingness.length ?? 0) > 0 && <p className="muted">{commandCenter!.missingness.join(' ')}</p>}</Panel>
    <Panel title="Public intelligence" action={<Button variant="ghost" onClick={onIntelligence}>View Intelligence</Button>}><p className="monitor-intro">Stored public scenarios demonstrate evidence workflows. They are curated public material, not today’s live collection.</p>{curated.length ? <div className="seller-signal-list curated-reference-list">{curated.map(brief => <SignalBriefCard key={brief.context_id ?? brief.id} brief={brief} accountName={name} onAccount={onAccount} onUseInOmni={useBrief} selected={selectedBriefContextId === (brief.assessment_id ?? brief.context_id ?? brief.id)} />)}</div> : <Empty>No projected curated public evidence is available.</Empty>}{missingCuratedCount > 0 && <p className="muted">{missingCuratedCount} projected curated record{missingCuratedCount === 1 ? '' : 's'} could not be resolved from the current Intelligence payload; no substitute was shown.</p>}</Panel>
    </Disclosure>
    </>}
  </div>
}
