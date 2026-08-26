import { useEffect, useMemo, useState } from 'react'
import type { Account, OmniContext, Signal } from '../../types/api'
import { Button, Disclosure, Empty, EvidenceSource, FilterChip, Panel, SearchInput, SelectInput, State } from '../../components/UI'
import './intelligence.css'

type Filters = { customer: string; industry: string; kind: string; source: string; evidence: string }
const emptyFilters: Filters = { customer: '', industry: '', kind: '', source: '', evidence: '' }
const eventDate = (value?: string) => value ? new Date(value).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'Unavailable'
const sourceValidation = (state?: string) => ({ BROWSER_VERIFIED: 'Source opened and supported in a normal browser.', AUTOMATION_BLOCKED: 'Publisher controls blocked automated validation; the original official source is retained.', REPLACED_WITH_EQUIVALENT_OFFICIAL_SOURCE: 'A stable, equivalent official source replaced the original; provenance retains the original.', NEEDS_RESEARCH: 'Source validation still needs research.' }[state ?? ''])
const unique = (values: Array<string | undefined>) => [...new Set(values.filter((value): value is string => Boolean(value)))].sort((a, b) => a.localeCompare(b))
const normalize = (value?: string) => (value ?? '').toLocaleLowerCase()

function signalMatches(signal: Signal, account: Account | undefined, query: string, filters: Filters) {
  const searchable = [signal.title, signal.relevance_explanation, account?.name, account?.legal_name, ...(account?.industries ?? []), signal.source_tier, signal.kind, signal.evidence_state, signal.source_validation_state].map(normalize)
  if (query.trim() && !searchable.some(value => value.includes(normalize(query.trim())))) return false
  if (filters.customer && signal.account_id !== filters.customer) return false
  if (filters.industry && !account?.industries.includes(filters.industry)) return false
  if (filters.kind && signal.kind !== filters.kind) return false
  if (filters.source && signal.source_tier !== filters.source) return false
  if (filters.evidence && signal.evidence_state !== filters.evidence && signal.source_validation_state !== filters.evidence) return false
  return true
}

export function Intelligence({ signals, accounts, onAccount, onEventSelect, onOmniContext }: { signals: Signal[]; accounts: Account[]; onAccount: (id: string) => void; onEventSelect: (id?: string) => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) {
  const [selectedEventId, setSelectedEventId] = useState<string>()
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const accountById = useMemo(() => new Map(accounts.map(account => [account.id, account])), [accounts])
  const visible = useMemo(() => signals.filter(signal => signalMatches(signal, accountById.get(signal.account_id ?? ''), query, filters)), [accountById, filters, query, signals])
  const visibleRecordIds = useMemo(() => visible.slice(0, 50).map(signal => signal.id), [visible])
  const options = useMemo(() => ({ customers: accounts.filter(account => signals.some(signal => signal.account_id === account.id)).sort((a, b) => (a.name ?? '').localeCompare(b.name ?? '')), industries: unique(signals.flatMap(signal => accountById.get(signal.account_id ?? '')?.industries ?? [])), kinds: unique(signals.map(signal => signal.kind)), sources: unique(signals.map(signal => signal.source_tier)), evidence: unique(signals.flatMap(signal => [signal.evidence_state, signal.source_validation_state])) }), [accountById, accounts, signals])
  const activeFilters = useMemo(() => {
    const active: Record<string, string> = {}
    if (query.trim()) active.search_query = query.trim()
    if (filters.customer) active.account_id = filters.customer
    if (filters.industry) active.market = filters.industry
    if (filters.kind) active.signal_type = filters.kind
    if (filters.source) active.source = filters.source
    if (filters.evidence) active.evidence_state = filters.evidence
    return active
  }, [filters, query])
  useEffect(() => () => onEventSelect(undefined), [onEventSelect])
  useEffect(() => { onOmniContext({ active_filters: Object.keys(activeFilters).length ? activeFilters : undefined, visible_record_ids: visibleRecordIds }) }, [activeFilters, onOmniContext, visibleRecordIds])
  useEffect(() => () => onOmniContext({}), [onOmniContext])
  const selectEvent = (id: string) => { const next = selectedEventId === id ? undefined : id; setSelectedEventId(next); onEventSelect(next) }
  const clearEventSelection = () => { if (selectedEventId) { setSelectedEventId(undefined); onEventSelect(undefined) } }
  const setSearch = (value: string) => { clearEventSelection(); setQuery(value) }
  const setFilter = (key: keyof Filters, value: string) => { clearEventSelection(); setFilters(current => ({ ...current, [key]: value })) }
  const clearAll = () => { clearEventSelection(); setQuery(''); setFilters(emptyFilters) }
  const customerName = (id?: string) => accountById.get(id ?? '')?.name ?? 'Unresolved Customer'
  const filterLabels: Array<[keyof Filters, string]> = [['customer', filters.customer ? customerName(filters.customer) : ''], ['industry', filters.industry], ['kind', filters.kind.replaceAll('_', ' ')], ['source', filters.source.replaceAll('_', ' ')], ['evidence', filters.evidence.replaceAll('_', ' ')]]
  return <div className="surface intelligence-surface">
    <header className="page-title intelligence-title"><span className="eyebrow">Public evidence</span><h1>Intelligence</h1><p>Find what changed and why it matters.</p></header>
    <section className="intelligence-controls" aria-label="Intelligence search and filters">
      <SearchInput aria-label="Search Intelligence" placeholder="Search title, summary, Customer, industry, source, signal type…" value={query} onChange={event => setSearch(event.target.value)} />
      <div className="intelligence-filter-grid">
        <SelectInput aria-label="Filter Intelligence by Customer" value={filters.customer} onChange={event => setFilter('customer', event.target.value)}><option value="">All Customers & Prospects</option>{options.customers.map(account => <option key={account.id} value={account.id}>{account.name ?? account.legal_name}</option>)}</SelectInput>
        <SelectInput aria-label="Filter Intelligence by industry" value={filters.industry} onChange={event => setFilter('industry', event.target.value)}><option value="">All industries</option>{options.industries.map(value => <option key={value}>{value}</option>)}</SelectInput>
        <SelectInput aria-label="Filter Intelligence by signal type" value={filters.kind} onChange={event => setFilter('kind', event.target.value)}><option value="">All signal types</option>{options.kinds.map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</SelectInput>
        <SelectInput aria-label="Filter Intelligence by source" value={filters.source} onChange={event => setFilter('source', event.target.value)}><option value="">All sources</option>{options.sources.map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</SelectInput>
        <SelectInput aria-label="Filter Intelligence by evidence state" value={filters.evidence} onChange={event => setFilter('evidence', event.target.value)}><option value="">All evidence states</option>{options.evidence.map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</SelectInput>
      </div>
      {Object.keys(activeFilters).length > 0 && <div className="intelligence-active-filters" aria-label="Active Intelligence filters">
        {query.trim() && <FilterChip selected onClear={() => setSearch('')}>{`Search: ${query.trim()}`}</FilterChip>}
        {filterLabels.map(([key, label]) => label && <FilterChip key={key} selected onClear={() => setFilter(key, '')}>{label}</FilterChip>)}
        <Button variant="ghost" onClick={clearAll}>Clear all</Button>
      </div>}
    </section>
    <div className="intelligence-result-line" role="status"><strong>{visible.length}</strong> of {signals.length} governed signals</div>
    <Panel className="intelligence-feed-panel">
      {visible.length ? <div className="intelligence-signal-list">{visible.map(signal => {
        const account = accountById.get(signal.account_id ?? '')
        return <article className={`intelligence-signal ${selectedEventId === signal.id ? 'selected' : ''}`} key={signal.id}>
          <div className="intelligence-signal-head"><div><span className="eyebrow">{signal.kind.replaceAll('_', ' ')}</span><button className="intelligence-customer-link" disabled={!signal.account_id} onClick={() => signal.account_id && onAccount(signal.account_id)}>{customerName(signal.account_id)}</button></div><div className="intelligence-states"><State value="PUBLIC EVIDENCE" /><State value={signal.evidence_state} /></div></div>
          <h2>{signal.title}</h2>
          <p className="intelligence-context">{account ? [account.relationship === 'TARGET' ? 'Prospect' : 'Customer', ...account.industries].join(' · ') : 'Customer association unavailable'}</p>
          <p className="intelligence-meaning"><strong>Why it may matter:</strong> {signal.relevance_explanation}</p>
          <p className="intelligence-next-step"><strong>Next:</strong> Review the public evidence and explicit Customer context.</p>
          <Disclosure title={`Evidence · ${eventDate(signal.observed_at)} · ${signal.source_tier?.replaceAll('_', ' ') ?? 'Source unavailable'}`}><EvidenceSource title={signal.title} source={signal.source_tier} date={eventDate(signal.observed_at)} evidenceState={signal.evidence_state} validationState={signal.source_validation_state} url={signal.source_url} detail={sourceValidation(signal.source_validation_state)} /></Disclosure>
          <div className="card-actions intelligence-actions"><Button aria-pressed={selectedEventId === signal.id} variant={selectedEventId === signal.id ? 'primary' : 'secondary'} onClick={() => selectEvent(signal.id)}>{selectedEventId === signal.id ? 'Clear Omni event' : 'Use in Omni'}</Button>{signal.account_id && <Button variant="ghost" onClick={() => onAccount(signal.account_id!)}>Open Customer</Button>}</div>
        </article>
      })}</div> : <Empty>No governed Intelligence matches the current search and filters. Clear filters to restore results.</Empty>}
    </Panel>
  </div>
}
