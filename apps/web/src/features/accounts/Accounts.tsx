import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from '../../api/client'
import type { Account, Account360, AccountPlanning, AccountRelationships, Action, ActionPriority, Alert, OmniAssessmentSelection, OmniContext, SellerRelationshipEvidence, SellerRelationshipPath, Signal } from '../../types/api'
import { Button, Disclosure, Empty, EvidenceSource, FilterChip, FilterTrigger, MetadataRow, Notice, Panel, SearchInput, SelectInput, State, StatTile, StatusBadge, TextInput } from '../../components/UI'
import { GovernedExplanationDisclosure } from '../../components/GovernedExplanationDisclosure'
import './accounts.css'
import { RankedRelationships } from './RankedRelationships'
import { CommercialDecisions } from './CommercialDecisions'
import { CommercialRecords } from './CommercialRecords'
import { WorkbookFields } from './WorkbookFields'
import { TechnicalDecompositionSection } from '../../components/TechnicalDecompositionSection'

type Scope = 'RICH' | 'ALL'
type Classification = 'ALL' | 'CUSTOMER' | 'PROSPECT' | 'UNAVAILABLE'
type PartnershipScope = 'ALL' | 'EXCLUDE' | 'ONLY'
type SortKey = 'name' | 'classification' | 'industry' | 'attractiveness' | 'priority' | 'evidence'
type SortDirection = 'ascending' | 'descending'
export type PortfolioSnapshot = { query: string; scope: Scope; industry: string; entity: Classification; top100: boolean; partnershipScope?: PartnershipScope; shortlistOnly?: boolean; sortKey: SortKey; sortDirection: SortDirection; filtersOpen: boolean; page?: number }
const priorityRank: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 }
const humanize = (value: string) => value.replaceAll('_', ' ')
const accountName = (item: Account) => item.name ?? item.legal_name ?? item.id
const primaryIndustry = (item: Account) => item.industries[0] ?? 'Industry unavailable'
const classification = (item: Account): Exclude<Classification, 'ALL'> => item.relationship === 'CURRENT_CUSTOMER' || item.relationship === 'FORMER_CUSTOMER' ? 'CUSTOMER' : item.relationship === 'TARGET' || item.relationship === 'PROSPECT' ? 'PROSPECT' : 'UNAVAILABLE'
const classificationLabel = (item: Account) => classification(item) === 'UNAVAILABLE' ? 'Classification unavailable' : humanize(classification(item).toLowerCase())
const alertRenderKey = (alert: Alert) => `${alert.id}:${[...alert.evidence_ids].sort().join('|')}`
const score = (item: Account) => item.attractiveness == null ? null : Number(item.attractiveness)
// Coverage remains explicit in the attractiveness rationale metadata below.

function compareKnown<T>(left: T | null | undefined, right: T | null | undefined, compare: (a: T, b: T) => number, direction: SortDirection) {
  if (left == null && right == null) return 0
  if (left == null) return 1
  if (right == null) return -1
  const result = compare(left, right)
  return direction === 'ascending' ? result : -result
}
function evidenceLabel(item: Account) { return item.truth_state ? humanize(item.truth_state.toLowerCase()) : null }
function compareAccounts(a: Account, b: Account, key: SortKey, direction: SortDirection) {
  let result: number
  if (key === 'attractiveness') {
    const left = score(a); const right = score(b)
    result = compareKnown(left, right, (x, y) => x - y, direction)
  } else if (key === 'priority') {
    const left = a.prospect_research_priority?.toUpperCase(); const right = b.prospect_research_priority?.toUpperCase()
    result = compareKnown(left, right, (x, y) => (priorityRank[x] ?? 0) - (priorityRank[y] ?? 0), direction)
  } else {
    const left = key === 'name' ? accountName(a) : key === 'industry' ? (a.industries[0] ?? null) : key === 'classification' ? (classification(a) === 'UNAVAILABLE' ? null : classificationLabel(a)) : evidenceLabel(a)
    const right = key === 'name' ? accountName(b) : key === 'industry' ? (b.industries[0] ?? null) : key === 'classification' ? (classification(b) === 'UNAVAILABLE' ? null : classificationLabel(b)) : evidenceLabel(b)
    result = compareKnown(left, right, (x, y) => x.localeCompare(y, undefined, { sensitivity: 'base' }), direction)
  }
  if (result === 0) result = accountName(a).localeCompare(accountName(b), undefined, { sensitivity: 'base' }) || a.id.localeCompare(b.id)
  return result
}

const PAGE_SIZE = 50

function Portfolio({ accounts, initialSnapshot, onSnapshot, onSelect, onOmniContext }: { accounts: Account[]; initialSnapshot?: PortfolioSnapshot; onSnapshot?: (snapshot: PortfolioSnapshot) => void; onSelect: (id: string) => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) {
  const [query, setQuery] = useState(initialSnapshot?.query ?? '')
  const [scope, setScope] = useState<Scope>(initialSnapshot?.scope ?? 'RICH')
  const [industry, setIndustry] = useState(initialSnapshot?.industry ?? 'ALL')
  const [entity, setEntity] = useState<Classification>(initialSnapshot?.entity ?? 'ALL')
  const [top100, setTop100] = useState(initialSnapshot?.top100 ?? false)
  const [partnershipScope, setPartnershipScope] = useState<PartnershipScope>(initialSnapshot?.partnershipScope ?? 'ALL')
  const [shortlistOnly, setShortlistOnly] = useState(initialSnapshot?.shortlistOnly ?? false)
  const [planning, setPlanning] = useState<AccountPlanning>()
  const [planningError, setPlanningError] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>(initialSnapshot?.sortKey ?? 'name')
  const [sortDirection, setSortDirection] = useState<SortDirection>(initialSnapshot?.sortDirection ?? 'ascending')
  const [filtersOpen, setFiltersOpen] = useState(initialSnapshot?.filtersOpen ?? false)
  const [page, setPage] = useState(initialSnapshot?.page ?? 0)
  const paginationInputsReady = useRef(false)
  useEffect(() => { onSnapshot?.({ query, scope, industry, entity, top100, partnershipScope, shortlistOnly, sortKey, sortDirection, filtersOpen, page }) }, [query, scope, industry, entity, top100, partnershipScope, shortlistOnly, sortKey, sortDirection, filtersOpen, page, onSnapshot])
  useEffect(() => { const controller = new AbortController(); void api.accountPlanning(controller.signal).then(result => { setPlanning(result); setPlanningError(false) }).catch(error => { if (error?.name !== 'AbortError') setPlanningError(true) }); return () => controller.abort() }, [])
  const partnershipIds = useMemo(() => new Set(planning?.strategic_partnerships.map(item => item.account_id) ?? []), [planning])
  const shortlistIds = useMemo(() => new Set(planning?.shortlist.map(item => item.account_id) ?? []), [planning])
  const industries = useMemo(() => [...new Set(accounts.flatMap(item => item.industries))].sort(), [accounts])
  const classifications = useMemo(() => new Set(accounts.map(classification)), [accounts])
  const shown = useMemo(() => accounts
    .filter(item => scope === 'ALL' || item.is_rich_scenario)
    .filter(item => industry === 'ALL' || item.industries.includes(industry))
    .filter(item => entity === 'ALL' || classification(item) === entity)
    .filter(item => !top100 || item.btx_top_100)
    .filter(item => partnershipScope === 'ALL' || (partnershipScope === 'ONLY') === partnershipIds.has(item.id))
    .filter(item => !shortlistOnly || shortlistIds.has(item.id))
    .filter(item => `${accountName(item)} ${item.industries.join(' ')} ${item.location?.city ?? ''} ${item.location?.state ?? ''} ${item.prospect_research_priority ?? ''}`.toLowerCase().includes(query.trim().toLowerCase()))
    .map((item, index) => ({ item, index }))
    .sort((a, b) => compareAccounts(a.item, b.item, sortKey, sortDirection) || a.index - b.index)
    .map(({ item }) => item), [accounts, entity, industry, partnershipIds, partnershipScope, query, scope, shortlistIds, shortlistOnly, sortDirection, sortKey, top100])
  useEffect(() => {
    if (paginationInputsReady.current) setPage(0)
    else paginationInputsReady.current = true
  }, [entity, industry, partnershipScope, query, scope, shortlistOnly, sortDirection, sortKey, top100])
  const activeFilters = useMemo(() => ({ ...(scope === 'RICH' ? { account_scope: 'RICH' } : {}), ...(industry === 'ALL' ? {} : { market: industry }), ...(entity === 'ALL' ? {} : { classification: entity }), ...(top100 ? { btx_top_100: 'true' } : {}), ...(partnershipScope === 'ALL' ? {} : { strategic_partnership: partnershipScope }), ...(shortlistOnly ? { saved_shortlist: 'true' } : {}) }), [entity, industry, partnershipScope, scope, shortlistOnly, top100])
  const pageCount = Math.max(1, Math.ceil(shown.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const paged = useMemo(() => shown.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE), [safePage, shown])
  const visibleRecordIds = useMemo(() => paged.map(account => account.id), [paged])
  const hasFilters = scope !== 'ALL' || industry !== 'ALL' || entity !== 'ALL' || top100 || partnershipScope !== 'ALL' || shortlistOnly
  const clearFilters = () => { setScope('ALL'); setIndustry('ALL'); setEntity('ALL'); setTop100(false); setPartnershipScope('ALL'); setShortlistOnly(false) }
  const sortBy = (key: SortKey) => { setPage(0); if (sortKey === key) setSortDirection(value => value === 'ascending' ? 'descending' : 'ascending'); else { setSortKey(key); setSortDirection(key === 'name' || key === 'classification' || key === 'industry' || key === 'evidence' ? 'ascending' : 'descending') } }
  const direction = (key: SortKey) => sortKey === key ? sortDirection : 'none'
  useEffect(() => { onOmniContext({ active_filters: Object.keys(activeFilters).length ? activeFilters : undefined, visible_record_ids: visibleRecordIds }) }, [activeFilters, onOmniContext, visibleRecordIds])
  useEffect(() => () => onOmniContext({}), [onOmniContext])
  return <div className="surface accounts-surface">
    <header className="page-title accounts-title"><span className="eyebrow">Customer portfolio</span><h1>Customers &amp; Prospects</h1><p>Prioritize researched Customers and Prospects using canonical identity, supported classifications, and governed Customer Attractiveness.</p></header>
    <div className="portfolio-summary-grid" aria-label="Customer Portfolio summary"><StatTile label="Current view" value={shown.length} detail="Customers and Prospects matching this view" /><StatTile label="Curated scenarios" value={shown.filter(item => item.is_rich_scenario).length} detail="Governed seller scenarios in this view" /><StatTile label="Scores available" value={shown.filter(item => score(item) != null).length} detail="Deterministic attractiveness outputs" /></div>
    <Panel className="portfolio-panel" title="Customer Portfolio" action={<span className="panel-kicker">{shown.length} results</span>}>
      <div className="portfolio-toolbar"><SearchInput aria-label="Search Customers and Prospects" placeholder="Search Customer, industry, or location" value={query} onChange={event => setQuery(event.target.value)} /><FilterTrigger active={hasFilters} aria-controls="portfolio-filters" aria-expanded={filtersOpen} onClick={() => setFiltersOpen(value => !value)}>Filters{hasFilters ? ` (${Object.keys(activeFilters).length})` : ''}</FilterTrigger><SelectInput className="portfolio-sort-select" aria-label="Sort Customers and Prospects" value={`${sortKey}:${sortDirection}`} onChange={event => { const [key, order] = event.target.value.split(':') as [SortKey, SortDirection]; setSortKey(key); setSortDirection(order) }}><option value="name:ascending">Name A–Z</option><option value="name:descending">Name Z–A</option><option value="attractiveness:descending">Attractiveness high–low</option><option value="attractiveness:ascending">Attractiveness low–high</option><option value="priority:descending">Priority high–low</option><option value="industry:ascending">Industry A–Z</option></SelectInput></div>
      <div id="portfolio-filters" className={`portfolio-filter-panel ${filtersOpen ? 'open' : ''}`}>
        <div className="portfolio-filter-field filters"><span>Scope</span><SelectInput aria-label="Customer scope" value={scope} onChange={event => setScope(event.target.value as Scope)}><option value="RICH">Curated scenarios</option><option value="ALL">All researched Customers and Prospects</option></SelectInput></div>
        <FilterGroup label="Classification"><FilterChip selected={entity === 'ALL'} onClick={() => setEntity('ALL')}>All classifications</FilterChip>{classifications.has('CUSTOMER') && <FilterChip selected={entity === 'CUSTOMER'} onClick={() => setEntity('CUSTOMER')}>Customer</FilterChip>}{classifications.has('PROSPECT') && <FilterChip selected={entity === 'PROSPECT'} onClick={() => setEntity('PROSPECT')}>Prospect</FilterChip>}{classifications.has('UNAVAILABLE') && <FilterChip selected={entity === 'UNAVAILABLE'} onClick={() => setEntity('UNAVAILABLE')}>Classification unavailable</FilterChip>}</FilterGroup>
        <FilterGroup label="Industry"><FilterChip selected={industry === 'ALL'} onClick={() => setIndustry('ALL')}>All industries</FilterChip>{industries.map(value => <FilterChip selected={industry === value} key={value} onClick={() => setIndustry(value)}>{value}</FilterChip>)}</FilterGroup>
        <FilterGroup label="Reference classifications"><FilterChip selected={top100} onClick={() => { setTop100(value => !value); setScope('ALL') }}>BTX Top 100</FilterChip></FilterGroup>
        <FilterGroup label="Strategic partnerships"><FilterChip selected={partnershipScope === 'ALL'} onClick={() => setPartnershipScope('ALL')}>All (Customers &amp; Prospects)</FilterChip><FilterChip selected={partnershipScope === 'EXCLUDE'} onClick={() => setPartnershipScope('EXCLUDE')}>Exclude partnerships</FilterChip><FilterChip selected={partnershipScope === 'ONLY'} onClick={() => setPartnershipScope('ONLY')}>Only partnerships</FilterChip></FilterGroup>
        <FilterGroup label="Saved planning"><FilterChip selected={shortlistOnly} onClick={() => setShortlistOnly(value => !value)}>My growth &amp; research shortlist</FilterChip></FilterGroup>
      </div>
      {planningError && <Notice tone="warning">Saved planning filters are temporarily unavailable. Customer records remain visible unless a saved filter is selected.</Notice>}
      {hasFilters && <div className="portfolio-active-filters" aria-label="Active Portfolio filters"><span>Applied</span>{scope === 'RICH' && <FilterChip selected onClear={() => setScope('ALL')}>Curated scenarios</FilterChip>}{top100 && <FilterChip selected onClear={() => setTop100(false)}>BTX Top 100</FilterChip>}{partnershipScope !== 'ALL' && <FilterChip selected onClear={() => setPartnershipScope('ALL')}>{partnershipScope === 'ONLY' ? 'Only partnerships' : 'Exclude partnerships'}</FilterChip>}{shortlistOnly && <FilterChip selected onClear={() => setShortlistOnly(false)}>My shortlist</FilterChip>}{entity !== 'ALL' && <FilterChip selected onClear={() => setEntity('ALL')}>{entity === 'UNAVAILABLE' ? 'Classification unavailable' : humanize(entity.toLowerCase())}</FilterChip>}{industry !== 'ALL' && <FilterChip selected onClear={() => setIndustry('ALL')}>{industry}</FilterChip>}<Button variant="ghost" onClick={clearFilters}>Clear all filters</Button></div>}
      <div className="portfolio-table-scroll" tabIndex={0} aria-label="Scrollable Customers and Prospects table"><table className="portfolio-data-table" aria-label="Customers and Prospects"><thead><tr>{([['name', 'Customer / Prospect'], ['classification', 'Classification'], ['industry', 'Industry'], ['attractiveness', 'Attractiveness'], ['priority', 'Priority'], ['evidence', 'Evidence']] as Array<[SortKey, string]>).map(([key, title]) => <th key={key} scope="col" aria-sort={direction(key)}><button type="button" onClick={() => sortBy(key)}>{title}<span aria-hidden="true">{direction(key) === 'ascending' ? '↑' : direction(key) === 'descending' ? '↓' : '↕'}</span></button></th>)}</tr></thead><tbody>{paged.map(item => <tr key={item.id}><th scope="row" className="portfolio-name"><a href={`#/accounts/${encodeURIComponent(item.id)}`} onClick={event => { event.preventDefault(); onSelect(item.id) }}>{accountName(item)}</a><small>{item.location?.city && (item.location?.state ?? item.location?.region) ? `${item.location.city}, ${item.location.state ?? item.location.region}` : 'Location unavailable'}</small></th><td><StatusBadge value={classification(item)} kind="entity" label={classificationLabel(item)} />{item.btx_top_100 && <StatusBadge value="BTX Top 100" />}{partnershipIds.has(item.id) && <StatusBadge value="Strategic partnership" />}{shortlistIds.has(item.id) && <StatusBadge value="My shortlist" />}</td><td>{primaryIndustry(item)}</td><td className="portfolio-score">{item.attractiveness ?? 'Unavailable'}</td><td>{item.prospect_research_priority ? humanize(item.prospect_research_priority) : 'Unavailable'}</td><td><State value={item.truth_state ?? 'UNAVAILABLE'} /></td></tr>)}</tbody></table></div>
      {pageCount > 1 && <nav className="portfolio-pagination" aria-label="Customer table pages"><Button disabled={safePage === 0} onClick={() => setPage(Math.max(0, safePage - 1))}>Previous</Button><span>Page {safePage + 1} of {pageCount} · {shown.length} results</span><Button disabled={safePage + 1 >= pageCount} onClick={() => setPage(Math.min(pageCount - 1, safePage + 1))}>Next</Button></nav>}
      {shown.length === 0 && <Empty>No Customers or Prospects match the current search and filters. Clear filters or try a different search.</Empty>}
    </Panel>
  </div>
}

function FilterGroup({ label, children }: { label: string; children: ReactNode }) { return <div className="portfolio-filter-field"><span>{label}</span><div className="chips">{children}</div></div> }
export function Accounts(props: { accounts: Account[]; detail?: Account360; initialSnapshot?: PortfolioSnapshot; onSnapshot?: (snapshot: PortfolioSnapshot) => void; onSelect: (id: string) => void; onBack: () => void; onOmniContext: (context: Pick<OmniContext, 'selected_assessment' | 'active_filters' | 'visible_record_ids' | 'relationship_selection'>) => void }) { return props.detail ? <CustomerDetail key={props.detail.account.id} accounts={props.accounts} detail={props.detail} onSelect={props.onSelect} onBack={props.onBack} onOmniContext={props.onOmniContext} /> : <Portfolio accounts={props.accounts} initialSnapshot={props.initialSnapshot} onSnapshot={props.onSnapshot} onSelect={props.onSelect} onOmniContext={props.onOmniContext} /> }
function Signals({ items, selectedAssessmentId, onUseInOmni }: { items: Signal[]; selectedAssessmentId?: string; onUseInOmni: (selection?: OmniAssessmentSelection) => void }) { return items.length ? <div className="evidence-list">{items.map(item => { const brief = item.business_briefing; const accountId = brief?.canonical_account_ids[0]; const selection = brief?.assessment_id && brief.assessment_version && accountId ? { assessment_id: brief.assessment_id, assessment_version: brief.assessment_version, event_id: brief.id, account_id: accountId } : undefined; const selected = Boolean(selection && selection.assessment_id === selectedAssessmentId); return <article key={item.id}><EvidenceSource title={brief?.headline ?? item.title} source={item.source_tier ?? 'Public source'} date={item.observed_at} evidenceState={item.evidence_state} validationState={item.source_validation_state} url={item.source_url} detail={brief?.why_it_may_matter ?? item.relevance_explanation} />{brief && <><p><strong>Next:</strong> {brief.recommended_action ?? 'Informational only; no seller action is established.'}</p><TechnicalDecompositionSection technical={brief.technical_opportunity ?? brief.evidence_package?.technical_decomposition} /></>}{selection && <Button variant={selected ? 'primary' : 'ghost'} aria-pressed={selected} onClick={() => onUseInOmni(selected ? undefined : selection)}>{selected ? 'Clear Omni event' : 'Use in Omni'}</Button>}</article> })}</div> : <Empty>No current public Intelligence assessment is available.</Empty> }

const relationshipDate = (value?: string) => value ? new Date(value).toLocaleDateString('en-US', { timeZone: 'UTC' }) : undefined
function RelationshipEvidence({ item, path }: { item: SellerRelationshipEvidence; path: SellerRelationshipPath }) {
  const truth = item.classification === 'INTERNAL_COMMERCIAL' || item.data_mode === 'SAMPLE' ? 'SAMPLE BTX relationship context.' : 'Supports this canonical relationship path.'
  const reference = item.source_record_id ? `Source reference: ${item.source_record_id}.` : 'Source reference unavailable.'
  return <EvidenceSource title={path.connection_label} source={item.source_system ?? path.truth_label} date={relationshipDate(item.observed_at)} evidenceState={item.evidence_state} validationState={path.presentation_state} url={item.source_url} detail={`${truth} ${reference}`} />
}
function SellerRelationshipCard({ path }: { path: SellerRelationshipPath }) {
  return <article className="seller-relationship-card">
    <ol className="seller-relationship-chain" aria-label={path.summary}>{path.steps.map((step, index) => <li key={step.id}><strong>{step.display_name}</strong>{index < path.steps.length - 1 && <span aria-hidden="true">→</span>}</li>)}</ol>
    <div className="seller-relationship-meta"><StatusBadge value={path.direct ? 'DIRECT' : 'INDIRECT'} kind="relationship" /><State value={path.evidence_state} /><span>{path.step_count} canonical {path.step_count === 1 ? 'step' : 'steps'}</span></div>
    <p><strong>Connection:</strong> {path.connection_label}</p>
    <p><strong>Why it matters:</strong> {path.why_it_matters}</p><p><strong>Governed status:</strong> {path.seller_rationale}</p>
    {path.validation_requirements.length > 0 && <Notice tone="warning" title="Validate before use">{path.validation_requirements.join(' ')}</Notice>}
    {path.suggested_move && <p className="seller-relationship-move"><strong>Suggested move:</strong> {path.suggested_move}</p>}
    <Disclosure title={`Evidence · ${path.truth_label} · ${path.evidence.length} ${path.evidence.length === 1 ? 'source' : 'sources'}`}>
      {path.evidence.length ? <div className="seller-relationship-evidence">{path.evidence.map((item, index) => <RelationshipEvidence key={`${path.path_id}:${index}`} item={item} path={path} />)}</div> : <Empty>No supporting source is currently attached. This path must not be treated as validated.</Empty>}
    </Disclosure>
    <GovernedExplanationDisclosure title="Why this relationship path may be useful" explanation={path.governed_explanation} />
  </article>
}


function RelationshipIntelligence({ accountId, onOmniContext }: { accountId: string; onOmniContext: (context: Pick<OmniContext, 'relationship_selection'>) => void }) {
  const [relationships, setRelationships] = useState<AccountRelationships>(); const [error, setError] = useState(false); const [view, setView] = useState<'validated' | 'needs_validation'>('validated')
  useEffect(() => { let active = true; void api.relationships(accountId).then(result => { if (active) setRelationships(result) }).catch(() => { if (active) setError(true) }); return () => { active = false } }, [accountId])
  const projection = relationships?.seller_projection; const validated = projection?.validated ?? []; const needsValidation = projection?.needs_validation ?? []
  const shown = view === 'validated' ? validated : needsValidation
  return <div className="relationship-content">
    <RankedRelationships accountId={accountId} onOmniContext={onOmniContext} />
    <div className="relationship-intelligence-header"><div><span className="eyebrow">How this Customer is connected</span><p>Backend-governed paths explain the connection, evidence, business relevance, and a bounded next review.</p></div>{projection && <div className="relationship-counts"><span><strong>{projection.validated_count}</strong> validated</span><span><strong>{projection.needs_validation_count}</strong> to review</span></div>}</div>
    <Notice>Public professional contact research remains separate and does not establish a BTX relationship, introduction path, or relationship strength.</Notice>
    <p className="muted">Reference connections below retain their original evidence and explanations. Explore ranked routes in the canonical network above; these reference cards are not a second route ranking.</p>
    <div className="relationship-view-toggle" role="tablist" aria-label="Relationship reference view"><button role="tab" aria-selected={view === 'validated'} className={view === 'validated' ? 'selected' : ''} onClick={() => setView('validated')}>Validated connections</button><button role="tab" aria-selected={view === 'needs_validation'} className={view === 'needs_validation' ? 'selected' : ''} onClick={() => setView('needs_validation')}>Connections to review</button></div>
    {!relationships && !error && <p className="relationship-intelligence-loading">Loading canonical relationship records…</p>}
    {error && <Empty>Canonical relationship records could not be loaded for this Customer. No relationship conclusion is shown.</Empty>}
    {relationships && shown.length === 0 && <Empty>{view === 'validated' ? 'No eligible validated connection is currently available for this Customer.' : 'No connection requiring validation is currently available for this Customer.'} This does not establish a real-world absence.</Empty>}
    {shown.length > 0 && <div className="seller-relationship-list">{shown.map(path => <SellerRelationshipCard key={path.path_id} path={path} />)}</div>}
    {projection && (projection.omitted_count > 0 || projection.unusable_count > 0) && <p className="muted">{projection.omitted_count ? `${projection.omitted_count} additional eligible path(s) are omitted from this bounded view. ` : ''}{projection.unusable_count ? `${projection.unusable_count} unusable path(s) are excluded from seller planning.` : ''}</p>}
  </div>
}

function useMobileCustomerLayout() { const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches); useEffect(() => { const media = window.matchMedia('(max-width: 760px)'); const update = () => setMobile(media.matches); media.addEventListener('change', update); return () => media.removeEventListener('change', update) }, []); return mobile }
function CustomerSection({ title, summary, children, defaultOpen = false, className = '' }: { title: string; summary?: string; children: ReactNode; defaultOpen?: boolean; className?: string }) { const mobile = useMobileCustomerLayout(); return <div className={`customer-section ${className}`}>{mobile ? <Disclosure title={<span>{title}{summary && <small>{summary}</small>}</span>} defaultOpen={defaultOpen}>{children}</Disclosure> : <Panel title={title} action={summary ? <span className="panel-kicker">{summary}</span> : undefined}>{children}</Panel>}</div> }
const money = (value: number | null | undefined, currency = 'USD') => value == null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value / 100)
function SourceState({ label, state }: { label: string; state: { data_mode: string; source_state: string } }) { const message = state.source_state === 'AVAILABLE' ? `${label} context available` : state.source_state === 'NO_LINKED_DATA' ? `No ${label} record is linked to this canonical Customer.` : state.source_state === 'NOT_CONFIGURED' ? `${label} integration is not configured.` : `${label} context is currently unavailable.`; return <MetadataRow label={label} value={`${state.data_mode} · ${message}`} /> }
function Commercial360({ detail }: { detail: Account360 }) { const view = detail.customer_360; const sourceStates = detail.commercial_source_states; return <CustomerSection title="Commercial context" summary={view.commercial.source_state.data_mode}><SourceState label="Commercial" state={view.commercial.source_state ?? sourceStates.commercial} /><SourceState label="Quotes / RFQs" state={view.quotes.source_state ?? sourceStates.paperless} /><SourceState label="Orders" state={view.orders.source_state ?? sourceStates.orders} />{view.commercial.records.length ? <div className="card-list">{view.commercial.records.map(row => <div className="line" key={row.business_unit ?? row.id}><span><strong>{row.business_unit ?? 'Business unit unavailable'}</strong><small>TTM revenue {money(row.ttm_revenue_minor, row.currency)} · bookings {money(row.ttm_bookings_minor, row.currency)}</small></span><State value={row.provenance?.data_mode ?? 'UNAVAILABLE'} /></div>)}</div> : <Empty>{view.commercial.missing ?? 'Commercial context unavailable.'}</Empty>}{view.quotes.records.length ? <Disclosure title={`Recent quotes / RFQs · ${view.quotes.records.length}`}><div className="card-list">{view.quotes.records.map(row => <div className="line" key={row.id}><span><strong>{row.id}</strong><small>{row.quoted_at} · {money(row.value_minor, row.currency)} · {row.business_unit ?? 'BU unavailable'}</small></span><State value={row.status ?? 'UNAVAILABLE'} /></div>)}</div></Disclosure> : <p className="muted">{view.quotes.missing}</p>}{view.orders.records.length ? <Disclosure title={`Recent orders · ${view.orders.records.length}`}><div className="card-list">{view.orders.records.map(row => <div className="line" key={row.id}><span><strong>{row.id}</strong><small>{row.recent_order_date ?? 'Date unavailable'} · {money(row.amount_minor)} · {row.business_unit ?? 'BU unavailable'}</small></span><State value={row.status ?? 'UNAVAILABLE'} /></div>)}</div></Disclosure> : <p className="muted">{view.orders.missing}</p>}</CustomerSection> }
function OperationalRelevance({ detail }: { detail: Account360 }) { const view = detail.customer_360; return <CustomerSection title="Programs, components & capabilities" summary={`${view.programs.length} programs`}><p className="workspace-intro">Governed operational relevance explains where BTX may be able to serve this Customer or Prospect; it does not imply an active commercial relationship.</p>{view.programs.length ? <div className="card-list">{view.programs.map(row => <div className="line" key={row.id}><span><strong>{row.name}</strong><small>{row.system ?? 'System unavailable'} · {row.provenance?.data_mode ?? 'UNAVAILABLE'}</small></span><State value={row.evidence_state ?? 'UNAVAILABLE'} /></div>)}</div> : <Empty>{view.missingness.programs}</Empty>}<Disclosure title={`Components · ${view.components.length}`}><div className="evidence-list">{view.components.length ? view.components.map(row => <EvidenceSource key={row.id} title={row.name ?? row.id} source={(row.business_unit_ids ?? []).join(', ') || 'Business unit unavailable'} evidenceState={row.evidence_state} detail={`Program: ${row.program_id ?? 'Unavailable'}`} />) : <Empty>{view.missingness.capabilities}</Empty>}</div></Disclosure><Disclosure title={`Capabilities · ${view.capabilities.length}`}><div className="evidence-list">{view.capabilities.length ? view.capabilities.map(row => <EvidenceSource key={row.id} title={row.name ?? row.id} source={(row.business_unit_ids ?? []).join(', ') || 'Business unit unavailable'} evidenceState={row.provenance?.evidence_state} detail={row.description ?? 'Capability description unavailable'} />) : <Empty>{view.missingness.capabilities}</Empty>}</div></Disclosure></CustomerSection> }
function CrmContacts({ detail }: { detail: Account360 }) { const crm = detail.customer_360.crm; return <CustomerSection title="Known contacts & CRM" summary={crm.source_state.data_mode}><SourceState label="CRM" state={crm.source_state} />{crm.contacts.length ? <div className="evidence-list">{crm.contacts.map(row => <EvidenceSource key={row.id} title={row.name ?? row.role_family ?? row.id} source={row.provenance?.source_system ?? 'CRM'} evidenceState={row.provenance?.evidence_state} detail={`${row.title ?? row.role_family ?? 'Role unavailable'} · ${row.provenance?.data_mode ?? 'UNAVAILABLE'}`} />)}</div> : <Empty>{crm.missing ?? 'No linked CRM contacts.'}</Empty>}<MetadataRow label="CRM owner" value={crm.owner_id ?? 'Unassigned'} /><MetadataRow label="CRM activity" value={crm.activity_count ? `${crm.activity_count} records; last activity ${crm.last_activity_at ?? 'unavailable'}` : 'No linked activity'} /></CustomerSection> }
function CustomerActions({ accountId, refreshVersion }: { accountId: string; refreshVersion: number }) {
  const [items, setItems] = useState<Action[]>([])
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<ActionPriority>('MEDIUM')
  const [notice, setNotice] = useState('')
  const [pending, setPending] = useState(false)
  const [retry, setRetry] = useState(0)
  const [draftKey, setDraftKey] = useState(() => crypto.randomUUID())
  useEffect(() => {
    const controller = new AbortController()
    void api.actions(controller.signal).then(result => { if (!controller.signal.aborted) setItems(result.items.filter(item => item.account_id === accountId)) }).catch(() => { if (!controller.signal.aborted) setNotice('Actions could not be loaded. Previously displayed work may be outdated.') })
    return () => controller.abort()
  }, [accountId, refreshVersion, retry])
  const create = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!title.trim() || pending) return
    setPending(true)
    try {
      const item = await api.createAction({ account_id: accountId, title, priority, idempotency_key: draftKey })
      setItems(current => [item, ...current.filter(existing => existing.id !== item.id)])
      setTitle(''); setDraftKey(crypto.randomUUID()); setNotice('Internal Action created. No external system was changed.')
    } catch { setNotice('Creation was not confirmed. Retry the same draft to avoid duplicates; inspect Work if you changed a previously submitted draft.') }
    finally { setPending(false) }
  }
  return <CustomerSection title="Actions" summary={`${items.filter(item => ['OPEN', 'IN_PROGRESS'].includes(item.status)).length} active`}>
    <div className="card-list">{items.length ? items.map(item => <div className="line" key={item.id}><span><strong>{item.title}</strong><small>{item.owner_id ?? 'Unassigned'} · {item.due_date ?? 'No due date'} · {item.approval_status}</small></span><State value={item.status} /></div>) : <Empty>No Actions for this Customer or Prospect.</Empty>}</div>
    <button type="button" onClick={() => setRetry(n => n + 1)}>Refresh Actions</button>
    <form className="customer-action-form" onSubmit={event => void create(event)}><TextInput label="Create internal Action" disabled={pending} value={title} onChange={event => setTitle(event.target.value)} /><SelectInput aria-label="New Action priority" disabled={pending} value={priority} onChange={event => setPriority(event.target.value as ActionPriority)}><option>HIGH</option><option>MEDIUM</option><option>LOW</option></SelectInput><Button type="submit" variant="primary" disabled={pending || !title.trim()}>{pending ? 'Creating…' : 'Create Action'}</Button></form>
    {notice && <p className="muted" role="status">{notice}</p>}
  </CustomerSection>
}
function AccountPlanningPanel({ accountId }: { accountId: string }) {
  const [planning, setPlanning] = useState<AccountPlanning>()
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [kind, setKind] = useState<'GROWTH' | 'RESEARCH'>('RESEARCH')
  const [objective, setObjective] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const [partnershipReason, setPartnershipReason] = useState('')
  const [retry, setRetry] = useState(0)
  const draftTouched = useRef(false)
  const saved = planning?.shortlist_records.find(item => item.account_id === accountId)
  const current = planning?.shortlist.find(item => item.account_id === accountId)
  const designation = planning?.strategic_partnerships.find(item => item.account_id === accountId)
  const designationRecord = planning?.partnership_records.find(item => item.account_id === accountId)
  const planningGap = planning?.planning_gaps.find(item => item.account_id === accountId)
  useEffect(() => { const controller = new AbortController(); void api.accountPlanning(controller.signal).then(result => { if (controller.signal.aborted) return; setPlanning(result); setError(''); if (!draftTouched.current) { const item = result.shortlist_records.find(entry => entry.account_id === accountId); setKind(item?.kind ?? 'RESEARCH'); setObjective(item?.objective ?? ''); setTargetDate(item?.target_date ?? '') } }).catch(reason => { if (reason?.name !== 'AbortError') setError('Account planning could not be loaded. Retry without losing the current Customer context.') }); return () => controller.abort() }, [accountId, retry])
  const save = async (active: boolean) => {
    if (pending || (!current && !active) || objective.trim().length < 10) return
    setPending(true); setError('')
    try { await api.saveShortlist({ account_id: accountId, kind, objective: objective.trim(), target_date: targetDate || null, active, expected_version: saved?.version ?? null, idempotency_key: crypto.randomUUID() }); setRetry(value => value + 1) }
    catch { setError('The shortlist change was not confirmed. Reload the saved planning state before retrying.') }
    finally { setPending(false) }
  }
  const designate = async (designated: boolean) => {
    if (pending || partnershipReason.trim().length < 10) return
    setPending(true); setError('')
    try { await api.designatePartnership(accountId, { designated, reason: partnershipReason.trim(), expected_version: designationRecord?.version ?? null, idempotency_key: crypto.randomUUID() }); setPartnershipReason(''); setRetry(value => value + 1) }
    catch { setError('The designation was not confirmed. Manager permission and the current version are required.') }
    finally { setPending(false) }
  }
  return <CustomerSection title="Growth & research planning" summary={current ? `${humanize(current.kind)} shortlist` : designation ? 'Strategic partnership' : 'Not yet saved'}>
    {!planning && !error && <p>Loading saved planning…</p>}
    {designation && <Notice title="Strategic partnership designation">{designation.reason} Updated {relationshipDate(designation.updated_at)} by {designation.updated_by}.</Notice>}
    <div className="customer-action-form"><SelectInput aria-label="Shortlist purpose" value={kind} disabled={pending} onChange={event => { draftTouched.current = true; setKind(event.target.value as 'GROWTH' | 'RESEARCH') }}><option value="GROWTH">Growth pursuit</option><option value="RESEARCH">Research required</option></SelectInput><TextInput label="Planning objective" value={objective} disabled={pending} onChange={event => { draftTouched.current = true; setObjective(event.target.value) }} /><TextInput label="Target date" type="date" value={targetDate} disabled={pending} onChange={event => { draftTouched.current = true; setTargetDate(event.target.value) }} /><Button variant="primary" disabled={pending || objective.trim().length < 10} onClick={() => void save(true)}>{pending ? 'Saving…' : current ? 'Update shortlist' : 'Add to shortlist'}</Button>{current && <Button disabled={pending} onClick={() => void save(false)}>Remove from shortlist</Button>}</div>
    {planning?.can_manage_partnerships && <Disclosure title="Manager designation"><TextInput label="Audited designation reason" value={partnershipReason} disabled={pending} onChange={event => setPartnershipReason(event.target.value)} /><div className="card-actions"><Button disabled={pending || partnershipReason.trim().length < 10} onClick={() => void designate(!designation)}>{designation ? 'Remove strategic partnership' : 'Designate strategic partnership'}</Button></div></Disclosure>}
    {planningGap && <Disclosure title="Sales planning gap"><p>{planningGap.interpretation}</p><p><strong>Recorded TTM bookings:</strong> {planningGap.actual_bookings_minor == null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: planningGap.currency }).format(planningGap.actual_bookings_minor / 100)}</p><p><strong>Governed target:</strong> {planningGap.target_bookings_minor == null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: planningGap.currency }).format(planningGap.target_bookings_minor / 100)} · <strong>Calculated shortfall:</strong> {planningGap.shortfall_minor == null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: planningGap.currency }).format(planningGap.shortfall_minor / 100)}</p><small>{planningGap.status.replaceAll('_', ' ').toLowerCase()} · BUs {planningGap.business_unit_ids.join(', ') || 'unavailable'} · {planningGap.evidence_ids.length} monthly evidence records</small></Disclosure>}
    {current && <p className="muted">Saved for the signed-in user · target {current.target_date ?? 'not dated'} · version {current.version}. No forecast, acquisition, CRM write, or external communication is implied.</p>}
    {error && <Notice tone="warning">{error} <Button onClick={() => setRetry(value => value + 1)}>Retry</Button></Notice>}
  </CustomerSection>
}
function CustomerDetail({ accounts, detail, onSelect, onBack, onOmniContext }: { accounts: Account[]; detail: Account360; onSelect: (id: string) => void; onBack: () => void; onOmniContext: (context: Pick<OmniContext, 'selected_assessment' | 'relationship_selection'>) => void }) {
  const [workRevision, setWorkRevision] = useState(0)
  const [selectedAssessment, setSelectedAssessment] = useState<OmniAssessmentSelection>()
  const [relationshipSelection, setRelationshipSelection] = useState<OmniContext['relationship_selection']>()
  const handleRelationshipContext = useCallback((context: Pick<OmniContext, 'relationship_selection'>) => setRelationshipSelection(context.relationship_selection), [])
  useEffect(() => { onOmniContext({ selected_assessment: selectedAssessment, relationship_selection: relationshipSelection }) }, [onOmniContext, relationshipSelection, selectedAssessment])
  useEffect(() => () => onOmniContext({}), [onOmniContext])
  const [switchQuery, setSwitchQuery] = useState(''); const attractiveness = detail.account_attractiveness; const fit = detail.prospect_fit; const fitDisplay = fit?.applicable && fit.score_low != null && fit.score_high != null ? (fit.score ?? `${fit.score_low}–${fit.score_high}`) : null; const name = accountName(detail.account); const availableFactors = attractiveness.factors.filter(factor => !factor.missing)
  const switchResults = switchQuery ? accounts.filter(item => `${accountName(item)} ${item.industries.join(' ')}`.toLowerCase().includes(switchQuery.toLowerCase())).slice(0, 6) : []
  const choose = (id: string) => { setSwitchQuery(''); onSelect(id) }
  return <div className="surface account-detail-surface"><div className="account-workspace-navigation"><Button className="account-workspace-back" variant="ghost" onClick={onBack}>← Customers &amp; Prospects</Button><div className="account-switcher"><SearchInput aria-label="Switch Customer" placeholder="Search Customer, industry, or location" value={switchQuery} onChange={event => setSwitchQuery(event.target.value)} />{switchResults.length > 0 && <div className="account-switch-results" role="listbox" aria-label="Customer switcher results">{switchResults.map(item => <button type="button" role="option" aria-selected="false" className="account-row account-switch-result" key={item.id} onClick={() => choose(item.id)}><span><strong>{accountName(item)}</strong><small>{item.industries.join(' / ') || 'Industry unavailable'}</small></span><State value={item.truth_state ?? 'UNAVAILABLE'} /></button>)}</div>}</div></div><section className="account-workspace" aria-label={`${name} Customer workspace`}>
    <header className="account-workspace-header"><div className="account-workspace-heading"><span className="eyebrow">Customers &amp; Prospects / Customer 360</span><h1>{name}</h1><p>{detail.account.industries.join(' · ') || 'Industry unavailable'}</p></div><div className="account-workspace-states"><StatusBadge value={classification(detail.account)} kind="entity" label={classificationLabel(detail.account)} />{detail.account.btx_top_100 && <StatusBadge value="BTX Top 100" />}<State value={detail.truth_categories.public} /><State value={detail.truth_categories.btx} /></div></header>
    <section className="account-decision-zone" aria-label="Customer decision summary"><StatTile label={fit?.applicable ? 'Prospect Fit' : 'Opportunity Priority'} value={fit?.applicable ? (fitDisplay ?? 'Unavailable') : (attractiveness.score ?? 'Unavailable')} detail={fit?.applicable ? `${Number(fit.coverage) * 100}% input coverage${fit.score == null ? ' · bounded range' : ''}` : humanize(attractiveness.status)} /><StatTile label="Research priority" value={detail.prospect_research_priority ? humanize(detail.prospect_research_priority) : 'Unavailable'} detail="Canonical research priority" /><div className="account-why"><span className="eyebrow">Why this Customer matters</span><p>{detail.reason_for_attention ?? 'No current reason for attention is available.'}</p><strong>Next review</strong><p>{detail.recommended_next_step ?? 'No governed next step is currently available.'}</p></div></section>
    <div className="account-primary-grid"><CustomerSection className="attention-section" title="What needs attention" summary={`${detail.alerts.length} governed alerts`} defaultOpen>{detail.alerts.length ? <div className="card-list">{detail.alerts.map(alert => <div className="workspace-attention" key={alertRenderKey(alert)}><State value={alert.severity} /><strong>{humanize(alert.type)}</strong><p>{alert.trigger_reason}</p><small>{alert.recommended_action}</small></div>)}</div> : <Empty>No governed alert is currently open for this Customer.</Empty>}</CustomerSection><Commercial360 detail={detail} /></div>
    <div className="account-secondary-grid"><GovernedExplanationDisclosure title="Why this Customer stands out" explanation={detail.governed_explanation} /><OperationalRelevance detail={detail} /><CrmContacts detail={detail} /><CustomerSection title="Recent intelligence" summary="Canonical public evidence"><Signals items={detail.customer_360.intelligence} selectedAssessmentId={selectedAssessment?.assessment_id} onUseInOmni={setSelectedAssessment} /></CustomerSection><CustomerSection title="Public professional contact research" summary={`${detail.public_contacts.length} records`}>{detail.public_contacts.length ? <div className="evidence-list">{detail.public_contacts.map(contact => <EvidenceSource key={`${contact.contact_type}-${contact.name ?? contact.role_family}`} title={contact.name ?? contact.role_family} source="Public professional research" date={relationshipDate(contact.provenance?.last_verified_at)} evidenceState={contact.verification_state} url={contact.source_url} detail={<>{contact.title_or_function ?? contact.role_family}{contact.contact_type === 'PUBLIC_CONTACT_CANDIDATE' && <> · Public role candidate; no introduction or buyer access is established. Date is the source observation.</>}</>} />)}</div> : <Empty>{`No verified public contact is available. Role-family target: ${detail.account.contact_role_families?.join(', ') ?? 'procurement / engineering'}.`}</Empty>}</CustomerSection><CustomerSection title="Canonical facilities" summary={`${detail.customer_360.facilities.length} linked`}>{detail.customer_360.facilities.length ? <div className="evidence-list">{detail.customer_360.facilities.map(facility => <EvidenceSource key={facility.id} title={facility.name ?? facility.id} source={`${facility.city ?? 'City unavailable'}, ${facility.region ?? 'Region unavailable'}`} evidenceState={facility.verification_state} url={facility.source_url} detail={facility.facility_type} />)}</div> : <Empty>{detail.customer_360.missingness.facilities}</Empty>}</CustomerSection>{fit?.applicable ? <CustomerSection title="Prospect Fit rationale & missingness" summary={fit.score == null ? `${fitDisplay ?? 'Unavailable'} range` : fit.score}><Notice title="Prospect Fit · deterministic rubric">A 0–100 fit score, not a probability. Missing factors are not reweighted; the range shows the known total through the maximum possible total.</Notice><MetadataRow label="Input coverage" value={`${Number(fit.coverage) * 100}%`} /><MetadataRow label="Configuration" value={fit.configuration_version} /><div className="factor-list">{fit.factors.map(factor => <div className="factor-row" key={factor.name}><span><strong>{factor.label} · {factor.weight}%</strong><small>{factor.reason}</small></span><strong>{factor.points ?? '—'}</strong></div>)}</div>{fit.missingness.length > 0 && <Notice tone="warning" title="Research needed">{fit.missingness.join(', ')}</Notice>}</CustomerSection> : <CustomerSection title="Opportunity Priority rationale & missingness" summary={humanize(attractiveness.status)}><Notice title="Opportunity Priority · scenario hypothesis">A 0–100 pursuit score, not a probability. It applies to a specific commercial pursuit and is unavailable when that scope is missing.</Notice><MetadataRow label="Input coverage" value={`${Number(attractiveness.coverage) * 100}%`} /><MetadataRow label="Configuration" value={attractiveness.configuration_version} /><p className="truth-note">{attractiveness.interpretation_note}</p>{attractiveness.exclusion_reason ? <p className="truth-note">{attractiveness.exclusion_reason}</p> : <div className="factor-list">{attractiveness.factors.map(factor => <div className="factor-row" key={factor.name}><span><strong>{humanize(factor.name)} · {Number(factor.configured_weight) * 100}%</strong><small>{factor.missing ? 'Missing canonical input' : `Contribution ${factor.contribution ?? 'Unavailable'} · input coverage ${Number(factor.input_coverage) * 100}%`}</small>{factor.gaps.length > 0 && <small>{factor.gaps.join(', ')}</small>}</span><strong>{factor.score ?? '—'}</strong></div>)}</div>}{!attractiveness.exclusion_reason && availableFactors.length === 0 && <Empty>No pursuit score factors are currently available.</Empty>}{attractiveness.missingness.length > 0 && <Notice tone="warning" title="Missing inputs">{attractiveness.missingness.join(', ')}</Notice>}</CustomerSection>}</div>
    <AccountPlanningPanel key={`planning:${detail.account.id}`} accountId={detail.account.id} />
    <CustomerSection className="account-workspace-relationship" title="Relationship Intelligence" summary="Canonical connections"><RelationshipIntelligence key={detail.account.id} accountId={detail.account.id} onOmniContext={handleRelationshipContext} /></CustomerSection>
    <CustomerSection title="Commercial decisions & follow-ups" summary="Evidence, qualification and action"><CommercialDecisions key={detail.account.id} accountId={detail.account.id} onWorkChanged={() => setWorkRevision(n => n + 1)} /></CustomerSection>
    <WorkbookFields key={`workbook:${detail.account.id}`} accountId={detail.account.id} />
    {detail.commercial_briefing && <CustomerSection title="Canonical records" summary="Complete enriched field disclosure"><CommercialRecords key={detail.account.id} accountId={detail.account.id} /></CustomerSection>}
    <CustomerActions key={detail.account.id} accountId={detail.account.id} refreshVersion={workRevision} />
    <CustomerSection title="Evidence & provenance" summary={humanize(detail.provenance.evidence_state)}><EvidenceSource title="Canonical Customer record" source={detail.provenance.source_record_id} evidenceState={detail.provenance.evidence_state} detail={detail.missingness.length ? `Missingness: ${detail.missingness.join(', ')}` : 'No additional projection missingness reported.'} /></CustomerSection>
  </section></div>
}
