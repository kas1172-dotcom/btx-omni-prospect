import { Fragment, useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { WorkspaceLocation } from '../../app/navigation'
import type { OmniContext } from '../../types/api'
import type { Opportunity } from '../../types/opportunities'
import { LoadingStatus } from '../../components/UI'
import { OpportunityDetail } from './OpportunityDetail'
import { MenuChoice, OpportunityMenu } from './OpportunityMenus'
import { OpportunityStatus, PriorityCell } from './PriorityCell'
import { category, clearFilters, compareCategory, filterRows, groupOptions, groupRows, hasFilters, marketOptions, money, nextSort, priorityOf, readView, sortOptions, sortRows, stageLabel, subtotal, viewLocation, type OpportunityView, type SavedView, type SortColumn } from './opportunityModel'
import searchIcon from './assets/search.svg'
import './opportunities.css'

export function Opportunities({ location, onLocationChange, onOmniContext }: { onOmniContext: (context: Pick<OmniContext, 'selected_account_id' | 'selected_commercial_opportunity'>) => void; location: WorkspaceLocation; onLocationChange: (next: WorkspaceLocation, mode?: 'push' | 'replace') => void }) {
  const fixture = import.meta.env.DEV && location.filters?.opportunity_fixture === 'demo'
  const [retry, setRetry] = useState(0)
  const key = `${fixture}:${retry}`
  const [loaded, setLoaded] = useState<{ key: string; rows: Opportunity[]; error?: boolean }>()
  const state = loaded?.key !== key ? 'loading' : loaded.error ? 'error' : 'ready'
  const rows = loaded?.key === key && !loaded.error ? loaded.rows : []
  useEffect(() => {
    const controller = new AbortController()
    const request = import.meta.env.DEV && fixture
      ? import('./opportunityFixture').then(module => ({ opportunities: module.opportunityFixture }))
      : api.opportunities(controller.signal)
    void request.then(result => { if (!controller.signal.aborted) setLoaded({ key, rows: result.opportunities }) }).catch(() => { if (!controller.signal.aborted) setLoaded({ key, rows: [], error: true }) })
    return () => controller.abort()
  }, [fixture, retry, key])
  const view = readView(location)
  const laneRows = rows.filter(row => row.lane === view.lane)
  const filtered = sortRows(filterRows(rows, view), view.sort)
  const groups = groupRows(filtered, view.group)
  const ordered = groups.flatMap(group => group.rows)
  const index = ordered.findIndex(row => row.opportunity_id === location.recordId)
  const selected = ordered[index]
  useEffect(() => {
    onOmniContext(selected && !fixture ? { selected_account_id: selected.account_id, selected_commercial_opportunity: { account_id: selected.account_id, opportunity_id: selected.opportunity_id, revision: selected.revision } } : {})
    return () => onOmniContext({})
  }, [onOmniContext, selected, fixture])
  const change = (patch: Partial<OpportunityView>, replace = false) => onLocationChange(viewLocation(location, { ...view, ...patch }), replace ? 'replace' : 'push')
  const open = (row: Opportunity) => onLocationChange(viewLocation(location, view, row.opportunity_id))
  const close = () => {
    onLocationChange(viewLocation(location, view))
    // Shared Drawer restores an initiating row. A reloaded deep link has no initiator.
    requestAnimationFrame(() => {
      if (document.activeElement !== document.body || document.querySelector('[role="dialog"]') || !selected) return
      const targets = document.querySelectorAll<HTMLElement>(`[data-opportunity-id="${CSS.escape(selected.opportunity_id)}"]`)
      Array.from(targets).find(node => node.getClientRects().length > 0)?.focus()
    })
  }
  const clear = () => onLocationChange(viewLocation(location, clearFilters(view)))
  const marketContent = <><h4>Markets</h4>{marketOptions(rows, view).map(o => <label className={o.count === 0 ? 'opp-zero' : ''} key={o.label}><input type="checkbox" checked={view.markets.includes(o.label)} disabled={o.count === 0 && !view.markets.includes(o.label)} onChange={() => change({ markets: view.markets.includes(o.label) ? view.markets.filter(v => v !== o.label) : [...view.markets, o.label] })} />{o.label}<span>{o.count}</span></label>)}<button className="opp-clear" onClick={() => change({ markets: [] })}>Clear markets</button></>
  const buContent = <><h4>Business unit</h4><MenuChoice selected={!view.bu} onClick={() => change({ bu: '' })}>All BUs</MenuChoice>{[...new Set([...rows.map(row => category(row.bu)), ...(view.bu ? [view.bu] : [])])].sort(compareCategory).map(bu => <MenuChoice key={bu} selected={view.bu === bu} onClick={() => change({ bu })}>{bu}</MenuChoice>)}</>
  const stageContent = <><h4>Stage</h4><MenuChoice selected={!view.stage} onClick={() => change({ stage: '' })}>All stages</MenuChoice>{[...new Set([...rows.map(row => row.stage), ...(view.stage ? [view.stage] : [])])].sort((a, b) => stageLabel(a).localeCompare(stageLabel(b))).map(stage => <MenuChoice key={stage} selected={view.stage === stage} onClick={() => change({ stage })}>{stageLabel(stage)}</MenuChoice>)}</>
  const columns: Array<[SortColumn | 'opportunity', string]> = [['company', 'Company'], ['opportunity', 'Opportunity'], ['market', 'Market'], ['stage', 'Stage'], ['value', 'Value'], ['priority', 'Priority'], ['status', 'Status']]
  const direction = (column: string) => (view.sort === 'default' ? 'priority-desc' : view.sort) === `${column}-asc` ? 'ascending' : (view.sort === 'default' ? 'priority-desc' : view.sort) === `${column}-desc` ? 'descending' : 'none'
  const groupHeader = (group: typeof groups[number]) => <button className="opp-group-toggle" aria-expanded={!view.collapsed.includes(group.name)} onClick={() => onLocationChange(viewLocation(location, { ...view, collapsed: view.collapsed.includes(group.name) ? view.collapsed.filter(v => v !== group.name) : [...view.collapsed, group.name] }, location.recordId))}><span aria-hidden="true">{view.collapsed.includes(group.name) ? '›' : '⌄'}</span><strong>{group.name}</strong><span className="opp-count">{group.rows.length}</span><span className="opp-group-subtotal">{group.subtotal}</span></button>
  const search = (label: string, placeholder: string) => <label className="opp-search"><img src={searchIcon} alt="" /><input type="search" aria-label={label} placeholder={placeholder} value={view.query} onChange={e => change({ query: e.target.value }, true)} /></label>
  return <main className="surface opportunity-workspace">
    <header className="opp-header"><div><span className="opp-eyebrow">Pursuit management</span><h1>Opportunities</h1><p>Tracked pursuits, split into customer expansion and prospect opportunities.</p></div><div className="opp-header-actions">{search('Search opportunities', 'Search')}<button className="opp-primary" onClick={() => window.dispatchEvent(new Event('btx:open-omni'))}>Ask Omni</button></div></header>
    {fixture && <p className="opp-fixture-notice" role="status">Development fixture · illustrative sample data · not live customer records</p>}
    <div className="opp-tabs-row"><div role="tablist" aria-label="Opportunity type" className="opp-tabs">{([['CUSTOMER_EXPANSION', 'Customer expansion'], ['PROSPECT', 'Prospect opportunities']] as const).map(([lane, label], i) => <button key={lane} role="tab" id={`opp-tab-${lane}`} tabIndex={view.lane === lane ? 0 : -1} aria-selected={view.lane === lane} aria-controls="opportunity-results" onKeyDown={e => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) { e.preventDefault(); const next = e.key === 'Home' ? 0 : e.key === 'End' ? 1 : 1 - i; change({ lane: next === 0 ? 'CUSTOMER_EXPANSION' : 'PROSPECT', collapsed: [] }); e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button')[next].focus() } }} onClick={() => change({ lane, collapsed: [] })}><span className={lane === 'PROSPECT' ? 'opp-desktop-label' : ''}>{label}</span>{lane === 'PROSPECT' && <span className="opp-mobile-label">Prospects</span>}<span className="opp-count">{rows.filter(row => row.lane === lane).length}</span></button>)}</div><div className="opp-saved" aria-label="Saved views">{([['all', 'All'], ['qualified-durable', 'Qualified and durable'], ['best-bets', 'Durable best bets']] as Array<[SavedView, string]>).map(([saved, label]) => <button key={saved} aria-pressed={view.saved === saved} onClick={() => change({ saved })}>{label}</button>)}</div></div>
    <div className="opp-metrics">{[['Tracked value', state === 'ready' ? subtotal(laneRows) : '—', `${laneRows.length} tracked pursuits · sized values only`], ['Qualified and durable', state === 'ready' ? laneRows.filter(row => row.gates?.qualified_and_durable).length : '—', 'Meets both qualification and durability gates'], ['Incomplete scores', state === 'ready' ? laneRows.filter(row => !priorityOf(row).complete).length : '—', 'Missing inputs shown as a priority range']].map(([label, value, caption]) => <section key={label}><h2>{label}</h2><strong>{value}</strong><p>{caption}</p></section>)}</div>
    <div className="opp-toolbar">{search('Filter opportunities', 'Filter by company or opportunity')}<div className="opp-desktop-filters"><OpportunityMenu label="Market" value={view.markets.length ? String(view.markets.length) : 'All'}>{marketContent}</OpportunityMenu><OpportunityMenu label="BU" value={view.bu || 'All'}>{buContent}</OpportunityMenu><OpportunityMenu label="Stage" value={view.stage ? stageLabel(view.stage) : 'All'}>{stageContent}</OpportunityMenu></div><div className="opp-toolbar-end"><div className="opp-mobile-filters"><OpportunityMenu label="Filters">{marketContent}{buContent}{stageContent}<button className="opp-clear" onClick={clear}>Clear filters</button></OpportunityMenu></div><OpportunityMenu label="Group by" value={groupOptions.find(([k]) => k === view.group)?.[1]}>{groupOptions.map(([group, label]) => <MenuChoice key={group} selected={view.group === group} onClick={() => change({ group, collapsed: [] })}>{label}</MenuChoice>)}</OpportunityMenu><OpportunityMenu label="Sort">{sortOptions.map(([sort, label]) => <MenuChoice key={sort} selected={view.sort === sort || (sort === 'default' && view.sort === 'priority-desc')} onClick={() => change({ sort })}>{label}</MenuChoice>)}</OpportunityMenu></div></div>
    {hasFilters(view) && <div className="opp-filter-count" role="status">{filtered.length} of {laneRows.length} shown{view.account && <span> · One account</span>}<button className="opp-clear" onClick={clear}>Clear filters</button></div>}
    <section id="opportunity-results" role="tabpanel" aria-labelledby={`opp-tab-${view.lane}`}>
      {state === 'loading' && <LoadingStatus>Loading opportunities…</LoadingStatus>}
      {state === 'error' && <div className="opp-empty" role="alert"><h2>Opportunities could not be loaded</h2><p>Try again to retrieve the current pursuits.</p><button onClick={() => setRetry(v => v + 1)}>Retry</button></div>}
      {state === 'ready' && !filtered.length && <div className="opp-empty"><h2>{laneRows.length ? 'No matches for these filters' : 'No opportunities in this lane'}</h2><p>{laneRows.length ? 'Try a different market, stage or search.' : 'No scoped pursuits are recorded in this category.'}</p>{hasFilters(view) && <button onClick={clear}>Clear filters</button>}</div>}
      {state === 'ready' && filtered.length > 0 && <><div className="opp-table-wrap"><table aria-label="Opportunities"><colgroup>{columns.map(([k]) => <col key={k} className={`opp-col-${k}`} />)}</colgroup><thead><tr>{columns.map(([column, label]) => <th key={column} className={`opp-cell-${column}`} scope="col" aria-sort={column === 'opportunity' ? undefined : direction(column)}>{column === 'opportunity' ? label : <button title={column === 'priority' ? 'Opportunity Priority: backend six-factor weighted composite. Click to cycle ascending, descending, default.' : `Sort by ${label}`} onClick={() => change({ sort: nextSort(view.sort, column) })}>{label}<span aria-hidden="true">{direction(column) === 'ascending' ? '↑' : direction(column) === 'descending' ? '↓' : '↕'}</span></button>}</th>)}</tr></thead><tbody>{groups.map(group => <Fragment key={group.name}>{group.name && <tr className="opp-group"><td colSpan={7}>{groupHeader(group)}</td></tr>}{(!group.name || !view.collapsed.includes(group.name)) && group.rows.map(row => <tr key={row.opportunity_id} data-opportunity-id={row.opportunity_id} tabIndex={0} className={selected === row ? 'selected' : ''} aria-label={`${row.account_name}, ${row.title}`} onClick={e => { e.currentTarget.focus(); open(row) }} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); open(row) } }}><td className="opp-company">{row.account_name}</td><td>{row.title}</td><td>{category(row.market)}</td><td className="opp-cell-stage">{stageLabel(row.stage)}</td><td className="opp-cell-value">{money(row.value_minor, row.currency)}</td><td className="opp-cell-priority"><PriorityCell row={row} /></td><td className="opp-cell-status"><OpportunityStatus row={row} /></td></tr>)}</Fragment>)}</tbody></table></div>
      <div className="opp-mobile-list">{groups.map(group => <Fragment key={group.name}>{group.name && groupHeader(group)}{(!group.name || !view.collapsed.includes(group.name)) && group.rows.map(row => <button key={row.opportunity_id} data-opportunity-id={row.opportunity_id} className={`opp-mobile-card ${selected === row ? 'selected' : ''}`} onClick={e => { e.currentTarget.focus(); open(row) }}><span className="opp-mobile-card-top"><strong>{row.account_name}</strong><OpportunityStatus row={row} /></span><strong className="opp-mobile-title">{row.title}</strong><span className="opp-mobile-meta">{category(row.market)} · {stageLabel(row.stage)} · {money(row.value_minor, row.currency)}</span><PriorityCell row={row} showBand /></button>)}</Fragment>)}</div></>}
    </section><p className="opp-footnote">Complete scores rank first, then incomplete scores by the top of their range. A range appears when scoring inputs are missing.</p>
    {selected && <OpportunityDetail row={selected} location={location} fixture={fixture} onClose={close} onPrevious={index > 0 ? () => open(ordered[index - 1]) : undefined} onNext={index < ordered.length - 1 ? () => open(ordered[index + 1]) : undefined} />}
  </main>
}
