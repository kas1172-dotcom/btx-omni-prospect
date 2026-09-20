import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { Account, AccountPlanning, OmniContext } from '../../types/api'
import type { PortfolioSnapshot } from './Accounts'
import { BookingsSparkline, HealthValue } from './ProfileMetrics'
import './profiles-redesign.css'

const views = ['All', 'Customers', 'Prospects', 'Needs attention', 'Strategic partners'] as const
type View = typeof views[number]
const customer = (row: Account) => ['CURRENT_CUSTOMER', 'FORMER_CUSTOMER'].includes(row.relationship)
const name = (row: Account) => row.name ?? row.legal_name ?? row.id
const defaults = { query: '', type: 'ALL', bu: 'ALL', market: 'ALL', geography: 'ALL', naics: 'ALL', top100: false, band: 'ALL', partnership: 'ALL', shortlist: false }
type Filters = typeof defaults
const load = () => { try { return JSON.parse(localStorage.getItem('profiles-view-v1') ?? '{}') as { view?: View; filters?: Filters; dense?: boolean } } catch { return {} } }

export function Portfolio({ accounts, initialSnapshot, onSnapshot, onSelect, onOmniContext }: { accounts: Account[]; initialSnapshot?: PortfolioSnapshot; onSnapshot?: (snapshot: PortfolioSnapshot) => void; onSelect: (id: string) => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) {
  const [view, setView] = useState<View>(() => { const value = load().view; return value && views.includes(value) ? value : 'All' })
  const [filters, setFilters] = useState<Filters>(() => ({ ...defaults, ...load().filters, ...(initialSnapshot?.query ? { query: initialSnapshot.query } : {}) }))
  const [dense, setDense] = useState(() => load().dense ?? false)
  const [planning, setPlanning] = useState<AccountPlanning>()
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [saved, setSaved] = useState<Filters | null>(() => { try { return JSON.parse(localStorage.getItem('profiles-saved-v1') ?? 'null') } catch { return null } })
  const [page, setPage] = useState(Math.max(0, (initialSnapshot?.page ?? 1) - 1))
  const [descending, setDescending] = useState(initialSnapshot?.sortDirection === 'descending')
  useEffect(() => { const controller = new AbortController(); void api.accountPlanning(controller.signal).then(setPlanning).catch(() => { if (!controller.signal.aborted) setError('Strategic partnership records could not be loaded.') }); return () => controller.abort() }, [retry])
  useEffect(() => { try { localStorage.setItem('profiles-view-v1', JSON.stringify({ view, filters, dense })) } catch { /* storage unavailable: current session remains usable */ } }, [view, filters, dense])
  useEffect(() => { onSnapshot?.({ query: filters.query, scope: 'ALL', industry: filters.market, entity: 'ALL', top100: filters.top100, sortKey: 'name', sortDirection: descending ? 'descending' : 'ascending', filtersOpen: false, page: page + 1 }) }, [filters, descending, page, onSnapshot])
  const partners = useMemo(() => new Set(planning?.strategic_partnerships.map(row => row.account_id) ?? []), [planning])
  const shortlist = useMemo(() => new Set(planning?.shortlist.map(row => row.account_id) ?? []), [planning])
  const inView = (row: Account, selected: View) => selected === 'All' || (selected === 'Customers' && customer(row)) || (selected === 'Prospects' && !customer(row)) || (selected === 'Needs attention' && ((row.open_items?.public ?? 0) + (row.open_items?.internal ?? 0) > 0)) || (selected === 'Strategic partners' && partners.has(row.id))
  const shown = accounts.filter(row => inView(row, view))
    .filter(row => filters.type === 'ALL' || (filters.type === 'Customers') === customer(row))
    .filter(row => filters.bu === 'ALL' || row.business_unit_ids?.includes(filters.bu))
    .filter(row => filters.market === 'ALL' || row.industries.includes(filters.market))
    .filter(row => filters.geography === 'ALL' || [row.location?.state, row.location?.region, row.location?.country].includes(filters.geography))
    .filter(row => filters.naics === 'ALL' || row.naics?.some(item => item.code === filters.naics))
    .filter(row => filters.band === 'ALL' || (row.health_band ?? 'Unavailable') === filters.band)
    .filter(row => !filters.shortlist || shortlist.has(row.id))
    .filter(row => !filters.top100 || row.btx_top_100)
    .filter(row => filters.partnership === 'ALL' || (filters.partnership === 'ONLY') === partners.has(row.id))
    .filter(row => `${name(row)} ${row.industries.join(' ')} ${row.location?.city ?? ''}`.toLowerCase().includes(filters.query.toLowerCase()))
    .sort((a, b) => name(a).localeCompare(name(b)) * (descending ? -1 : 1))
  const PAGE_SIZE = 50
  const pageCount = Math.max(1, Math.ceil(shown.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const paged = shown.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE)
  const ids = paged.map(row => row.id).join('|')
  const activeFilters = useMemo(() => ({
    ...(filters.market === 'ALL' ? {} : { market: filters.market }),
    ...(filters.bu === 'ALL' ? {} : { business_unit_id: filters.bu }),
    ...(filters.type === 'ALL' ? {} : { classification: filters.type === 'Customers' ? 'CUSTOMER' : 'PROSPECT' }),
    ...(filters.shortlist ? { saved_shortlist: 'true' } : {}),
    ...(filters.top100 ? { btx_top_100: 'true' } : {}),
    ...(filters.partnership === 'ALL' ? {} : { strategic_partnership: filters.partnership }),
  }), [filters])
  useEffect(() => { onOmniContext({ active_filters: Object.keys(activeFilters).length ? activeFilters : undefined, visible_record_ids: ids ? ids.split('|') : [] }) }, [activeFilters, ids, onOmniContext])
  useEffect(() => () => onOmniContext({}), [onOmniContext])
  const change = <K extends keyof Filters>(key: K, value: Filters[K]) => { setFilters(current => ({ ...current, [key]: value })); setPage(0) }
  const choices = (values: Array<string | undefined>) => [...new Set(values.filter((value): value is string => Boolean(value)))].sort()
  const select = (key: 'type' | 'bu' | 'market' | 'geography' | 'naics' | 'band', label: string, values: string[]) => <label className="profile-filter-chip">{label}<select aria-label={label} value={filters[key]} onChange={event => change(key, event.target.value)}><option value="ALL">All</option>{values.map(value => <option key={value}>{value}</option>)}</select></label>
  return <div className="surface accounts-surface profiles-redesign"><header className="page-title"><span className="eyebrow">Relationship workspace</span><h1>Accounts</h1><p>Customers, prospects and the next work that matters.</p></header>
    <aside className="profile-sample-banner"><strong>SAMPLE</strong> Commercial activity and relationship scenarios are simulated. Public evidence and per-account source states remain separate.</aside>
    <nav className="profile-saved-views" aria-label="Saved account views">{views.map(value => <button key={value} aria-pressed={view === value} onClick={() => { setView(value); setPage(0) }}>{value} <span>{value === 'Strategic partners' && !planning ? 'Unknown' : accounts.filter(row => inView(row, value)).length}</span></button>)}</nav>
    <div className="profile-toolbar"><input type="search" aria-label="Search Customers and Prospects" placeholder="Search accounts, markets or cities" value={filters.query} onChange={event => change('query', event.target.value)} />{select('type', 'Type', ['Customers', 'Prospects'])}{select('bu', 'BU', choices(accounts.flatMap(row => row.business_unit_ids ?? [])))}{select('market', 'Market', choices(accounts.flatMap(row => row.industries)))}<details className="profile-filter-popover"><summary>+ Filter</summary><div>{select('naics', 'NAICS (SAMPLE classification)', choices(accounts.flatMap(row => row.naics?.map(item => item.code) ?? [])))}{select('geography', 'Geography', choices(accounts.flatMap(row => [row.location?.state, row.location?.region, row.location?.country])))}{select('band', 'Health band', choices(accounts.map(row => row.health_band ?? 'Unavailable')))}<label><input type="checkbox" checked={filters.top100} onChange={event => change('top100', event.target.checked)} />Top 100</label><label><input type="checkbox" checked={filters.shortlist} onChange={event => change('shortlist', event.target.checked)} />My growth &amp; research shortlist</label><label>Strategic partnerships<select aria-label="Strategic partnerships" value={filters.partnership} onChange={event => change('partnership', event.target.value)}><option value="ALL">All (Customers &amp; Prospects)</option><option value="EXCLUDE">Exclude strategic partnerships</option><option value="ONLY">Strategic partnerships only</option></select></label></div></details><button aria-pressed={dense} onClick={() => setDense(value => !value)}>{dense ? 'Compact' : 'Comfortable'}</button></div>
    <div className="profile-active-filters">{(Object.keys(defaults) as Array<keyof Filters>).filter(key => filters[key] !== defaults[key]).map(key => <button key={key} aria-label={`Remove ${key} filter`} onClick={() => change(key, defaults[key])}>{key}: {String(filters[key])} ×</button>)}<button onClick={() => { setFilters(defaults); setPage(0) }}>Clear</button><button onClick={() => { try { localStorage.setItem('profiles-saved-v1', JSON.stringify(filters)); setSaved(filters) } catch { setError('This browser cannot persist a saved view.') } }}>Save view</button>{saved && <button onClick={() => { setFilters(saved); setPage(0) }}>Load saved view</button>}</div>
    {error && <p role="alert">{error} <button onClick={() => { setError(''); setRetry(n => n + 1) }}>Retry planning</button></p>}
    <div className={`portfolio-table-scroll ${dense ? 'profile-dense' : ''}`}><table className="portfolio-data-table" aria-label="Customers and Prospects"><thead><tr><th aria-sort={descending ? 'descending' : 'ascending'}><button onClick={() => { setDescending(value => !value); setPage(0) }}>Account {descending ? '↓' : '↑'}</button></th>{['Strategic partner', 'BU', 'Health', 'Fit', 'Open items', 'TTM bookings', 'Last CRM activity', 'Owner'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{paged.map((row, index) => <tr key={row.id} tabIndex={0} title={`Provenance: ${row.truth_state ?? 'Unknown'} · ${row.commercial_context_state ?? 'UNAVAILABLE'}`} onKeyDown={event => { if (event.target !== event.currentTarget) return; if (event.key === 'Enter') onSelect(row.id); if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); const rows = event.currentTarget.parentElement?.querySelectorAll<HTMLTableRowElement>(':scope > tr'); rows?.[Math.max(0, Math.min(paged.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))]?.focus() } }}><th scope="row"><div className="profile-account-cell"><span className="profile-monogram" aria-hidden="true">{name(row).split(' ').map(word => word[0]).slice(0, 2).join('')}</span><span><a href={`#/accounts/${encodeURIComponent(row.id)}`} onClick={event => { event.preventDefault(); onSelect(row.id) }}>{name(row)}</a><small>{customer(row) ? 'Customer' : 'Prospect'}</small></span></div></th><td>{planning ? partners.has(row.id) ? 'Yes' : '—' : 'Unknown'}</td><td>{row.business_unit_ids?.join(', ') || '—'}</td><td>{customer(row) ? <HealthValue decision={row.customer_health} band={row.health_band} /> : '—'}</td><td>{!customer(row) && row.prospect_fit?.applicable ? <span>{row.prospect_fit.score ?? `${row.prospect_fit.score_low ?? '?'}–${row.prospect_fit.score_high ?? '?'}`}<small>Data Coverage {(Number(row.prospect_fit.coverage) * 100).toFixed(0)}%</small></span> : '—'}</td><td>{row.open_items ? <span>{row.open_items.public} public<br />{row.open_items.internal} internal</span> : 'Unknown'}</td><td><BookingsSparkline months={row.bookings_monthly ?? []} delta={row.bookings_delta_3m_vs_prior_3m} /></td><td>{row.last_activity_at?.slice(0, 10) ?? 'Unknown'}</td><td>{row.owner_id ?? 'Unassigned'}</td></tr>)}</tbody></table></div>
    {!shown.length && <p>No accounts match this view. Try clearing filters.</p>}<nav className="profile-pagination" aria-label="Account pages"><span>{shown.length} accounts · Page {safePage + 1} of {pageCount}</span><button disabled={!safePage} onClick={() => setPage(safePage - 1)}>Previous</button><button disabled={safePage + 1 >= pageCount} onClick={() => setPage(safePage + 1)}>Next</button></nav>
  </div>
}
