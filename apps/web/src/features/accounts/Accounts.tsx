import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../../api/client'
import type { Account, Account360, AccountRelationships, Alert, OmniContext, SellerRelationshipEvidence, SellerRelationshipPath, Signal } from '../../types/api'
import { Button, Disclosure, Empty, EvidenceSource, FilterChip, FilterTrigger, MetadataRow, MobileListRow, Notice, Panel, ResponsiveTable, SearchInput, SelectInput, SortableHeader, State, StatTile, StatusBadge } from '../../components/UI'
import './accounts.css'

type Scope = 'RICH' | 'ALL'
type Classification = 'ALL' | 'CUSTOMER' | 'PROSPECT' | 'UNAVAILABLE'
type SortKey = 'name' | 'attractiveness' | 'priority' | 'industry'
type SortDirection = 'ascending' | 'descending'
const priorityRank: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 }
const humanize = (value: string) => value.replaceAll('_', ' ')
const accountName = (item: Account) => item.name ?? item.legal_name ?? item.id
const primaryIndustry = (item: Account) => item.industries[0] ?? 'Industry unavailable'
const classification = (item: Account): Exclude<Classification, 'ALL'> => item.relationship === 'CURRENT_CUSTOMER' || item.relationship === 'FORMER_CUSTOMER' ? 'CUSTOMER' : item.relationship === 'TARGET' ? 'PROSPECT' : 'UNAVAILABLE'
const classificationLabel = (item: Account) => classification(item) === 'UNAVAILABLE' ? 'Classification unavailable' : humanize(classification(item).toLowerCase())
const alertRenderKey = (alert: Alert) => `${alert.id}:${[...alert.evidence_ids].sort().join('|')}`
const score = (item: Account) => item.attractiveness == null ? null : Number(item.attractiveness)
// Coverage remains explicit in the attractiveness rationale metadata below.

function compareAccounts(a: Account, b: Account, key: SortKey, direction: SortDirection) {
  let result: number
  if (key === 'attractiveness') {
    const left = score(a); const right = score(b)
    result = left == null && right == null ? 0 : left == null ? 1 : right == null ? -1 : left - right
  } else if (key === 'priority') {
    const left = a.prospect_research_priority?.toUpperCase(); const right = b.prospect_research_priority?.toUpperCase()
    result = left == null && right == null ? 0 : left == null ? 1 : right == null ? -1 : (priorityRank[left] ?? 0) - (priorityRank[right] ?? 0)
  } else {
    const left = key === 'name' ? accountName(a) : primaryIndustry(a)
    const right = key === 'name' ? accountName(b) : primaryIndustry(b)
    result = left.localeCompare(right, undefined, { sensitivity: 'base' })
  }
  if (result === 0) result = accountName(a).localeCompare(accountName(b), undefined, { sensitivity: 'base' })
  return direction === 'ascending' ? result : -result
}

function Portfolio({ accounts, onSelect, onOmniContext }: { accounts: Account[]; onSelect: (id: string) => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) {
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState<Scope>('RICH')
  const [industry, setIndustry] = useState('ALL')
  const [entity, setEntity] = useState<Classification>('ALL')
  const [top100, setTop100] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [sortDirection, setSortDirection] = useState<SortDirection>('ascending')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const industries = useMemo(() => [...new Set(accounts.flatMap(item => item.industries))].sort(), [accounts])
  const classifications = useMemo(() => new Set(accounts.map(classification)), [accounts])
  const shown = useMemo(() => accounts
    .filter(item => scope === 'ALL' || item.is_rich_scenario)
    .filter(item => industry === 'ALL' || item.industries.includes(industry))
    .filter(item => entity === 'ALL' || classification(item) === entity)
    .filter(item => !top100 || item.btx_top_100)
    .filter(item => `${accountName(item)} ${item.industries.join(' ')} ${item.location?.city ?? ''} ${item.location?.state ?? ''} ${item.prospect_research_priority ?? ''}`.toLowerCase().includes(query.trim().toLowerCase()))
    .map((item, index) => ({ item, index }))
    .sort((a, b) => compareAccounts(a.item, b.item, sortKey, sortDirection) || a.index - b.index)
    .map(({ item }) => item), [accounts, entity, industry, query, scope, sortDirection, sortKey, top100])
  const activeFilters = useMemo(() => ({ ...(scope === 'RICH' ? { account_scope: 'RICH' } : {}), ...(industry === 'ALL' ? {} : { market: industry }), ...(entity === 'ALL' ? {} : { classification: entity }), ...(top100 ? { btx_top_100: 'true' } : {}) }), [entity, industry, scope, top100])
  const visibleRecordIds = useMemo(() => shown.slice(0, 50).map(account => account.id), [shown])
  const hasFilters = scope !== 'ALL' || industry !== 'ALL' || entity !== 'ALL' || top100
  const clearFilters = () => { setScope('ALL'); setIndustry('ALL'); setEntity('ALL'); setTop100(false) }
  const sortBy = (key: SortKey) => { if (sortKey === key) setSortDirection(value => value === 'ascending' ? 'descending' : 'ascending'); else { setSortKey(key); setSortDirection(key === 'name' || key === 'industry' ? 'ascending' : 'descending') } }
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
      </div>
      {hasFilters && <div className="portfolio-active-filters" aria-label="Active Portfolio filters"><span>Applied</span>{scope === 'RICH' && <FilterChip selected onClear={() => setScope('ALL')}>Curated scenarios</FilterChip>}{top100 && <FilterChip selected onClear={() => setTop100(false)}>BTX Top 100</FilterChip>}{entity !== 'ALL' && <FilterChip selected onClear={() => setEntity('ALL')}>{entity === 'UNAVAILABLE' ? 'Classification unavailable' : humanize(entity.toLowerCase())}</FilterChip>}{industry !== 'ALL' && <FilterChip selected onClear={() => setIndustry('ALL')}>{industry}</FilterChip>}<Button variant="ghost" onClick={clearFilters}>Clear all filters</Button></div>}
      <ResponsiveTable label="Customers and Prospects" header={<><SortableHeader direction={direction('name')} onClick={() => sortBy('name')}>Customer</SortableHeader><div role="columnheader">Classification</div><SortableHeader direction={direction('industry')} onClick={() => sortBy('industry')}>Industry</SortableHeader><SortableHeader direction={direction('attractiveness')} onClick={() => sortBy('attractiveness')}>Attractiveness</SortableHeader><SortableHeader direction={direction('priority')} onClick={() => sortBy('priority')}>Priority</SortableHeader><div role="columnheader">Evidence</div></>}>{shown.map(item => <button type="button" role="row" className="ui-table-row interactive account-row portfolio-table-row" key={item.id} onClick={() => onSelect(item.id)}><span role="cell" className="portfolio-name"><strong>{accountName(item)}</strong><small>{item.location?.city && (item.location?.state ?? item.location?.region) ? `${item.location.city}, ${item.location.state ?? item.location.region}` : 'Location unavailable'}</small></span><span role="cell"><StatusBadge value={classification(item)} kind="entity" label={classificationLabel(item)} />{item.btx_top_100 && <StatusBadge value="BTX Top 100" />}</span><span role="cell">{primaryIndustry(item)}</span><strong role="cell">{item.attractiveness ?? 'Unavailable'}</strong><span role="cell">{item.prospect_research_priority ? humanize(item.prospect_research_priority) : 'Unavailable'}</span><span role="cell"><State value={item.truth_state ?? 'UNAVAILABLE'} /></span></button>)}</ResponsiveTable>
      <div className="portfolio-mobile-list" aria-label="Customers and Prospects mobile list">{shown.map(item => <MobileListRow key={item.id} title={accountName(item)} metadata={<>{classificationLabel(item)} · {primaryIndustry(item)}{item.btx_top_100 ? ' · BTX Top 100' : ''}</>} tertiary={<>Attractiveness {item.attractiveness ?? 'unavailable'} · Priority {item.prospect_research_priority ? humanize(item.prospect_research_priority) : 'unavailable'} · {humanize(item.truth_state ?? 'UNAVAILABLE')}</>} onClick={() => onSelect(item.id)} />)}</div>
      {shown.length === 0 && <Empty>No Customers or Prospects match the current search and filters. Clear filters or try a different search.</Empty>}
    </Panel>
  </div>
}

function FilterGroup({ label, children }: { label: string; children: ReactNode }) { return <div className="portfolio-filter-field"><span>{label}</span><div className="chips">{children}</div></div> }
export function Accounts(props: { accounts: Account[]; detail?: Account360; onSelect: (id: string) => void; onBack: () => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) { return props.detail ? <CustomerDetail accounts={props.accounts} detail={props.detail} onSelect={props.onSelect} onBack={props.onBack} /> : <Portfolio accounts={props.accounts} onSelect={props.onSelect} onOmniContext={props.onOmniContext} /> }
function Signals({ items }: { items: Signal[] }) { return items.length ? <div className="evidence-list">{items.map(item => <EvidenceSource key={item.id} title={item.title} source={item.source_tier ?? 'Public source'} date={item.observed_at} evidenceState={item.evidence_state} validationState={item.source_validation_state} url={item.source_url} detail={item.relevance_explanation} />)}</div> : <Empty>No curated public event is available.</Empty> }

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
    <p><strong>Why it matters:</strong> {path.why_it_matters}</p>
    {path.suggested_move && <p className="seller-relationship-move"><strong>Suggested move:</strong> {path.suggested_move}</p>}
    <Disclosure title={`Evidence · ${path.truth_label} · ${path.evidence.length} ${path.evidence.length === 1 ? 'source' : 'sources'}`}>
      {path.evidence.length ? <div className="seller-relationship-evidence">{path.evidence.map((item, index) => <RelationshipEvidence key={`${path.path_id}:${index}`} item={item} path={path} />)}</div> : <Empty>No supporting source is currently attached. This path must not be treated as validated.</Empty>}
    </Disclosure>
  </article>
}

function RelationshipIntelligence({ accountId }: { accountId: string }) {
  const [relationships, setRelationships] = useState<AccountRelationships>(); const [error, setError] = useState(false); const [view, setView] = useState<'direct' | 'paths'>('direct')
  useEffect(() => { let active = true; void api.relationships(accountId).then(result => { if (active) setRelationships(result) }).catch(() => { if (active) setError(true) }); return () => { active = false } }, [accountId])
  const direct = relationships?.seller_direct_relationships.slice(0, 8) ?? []; const paths = relationships?.seller_paths.filter(path => !path.direct).slice(0, 6) ?? []
  const shown = view === 'direct' ? direct : paths
  return <div className="relationship-content">
    <div className="relationship-intelligence-header"><div><span className="eyebrow">How this Customer is connected</span><p>Canonical paths explain the connection, evidence, business relevance, and a bounded next review.</p></div>{relationships && <div className="relationship-counts"><span><strong>{direct.length}</strong> direct</span><span><strong>{paths.length}</strong> connected paths</span></div>}</div>
    <Notice>Public professional contact research remains separate and does not establish a BTX relationship, introduction path, or relationship strength.</Notice>
    <div className="relationship-view-toggle" role="tablist" aria-label="Relationship Intelligence view"><button role="tab" aria-selected={view === 'direct'} className={view === 'direct' ? 'selected' : ''} onClick={() => setView('direct')}>Direct connections</button><button role="tab" aria-selected={view === 'paths'} className={view === 'paths' ? 'selected' : ''} onClick={() => setView('paths')}>Connected paths</button></div>
    {!relationships && !error && <p className="relationship-intelligence-loading">Loading canonical relationship records…</p>}
    {error && <Empty>Canonical relationship records could not be loaded for this Customer. No relationship conclusion is shown.</Empty>}
    {relationships && shown.length === 0 && <Empty>{view === 'direct' ? 'No canonical direct connection is currently available for this Customer.' : 'No canonical connected path is currently available for this Customer.'} This does not establish a real-world absence.</Empty>}
    {shown.length > 0 && <div className="seller-relationship-list">{shown.map(path => <SellerRelationshipCard key={path.path_id} path={path} />)}</div>}
  </div>
}

function useMobileCustomerLayout() { const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches); useEffect(() => { const media = window.matchMedia('(max-width: 760px)'); const update = () => setMobile(media.matches); media.addEventListener('change', update); return () => media.removeEventListener('change', update) }, []); return mobile }
function CustomerSection({ title, summary, children, defaultOpen = false, className = '' }: { title: string; summary?: string; children: ReactNode; defaultOpen?: boolean; className?: string }) { const mobile = useMobileCustomerLayout(); return <div className={`customer-section ${className}`}>{mobile ? <Disclosure title={<span>{title}{summary && <small>{summary}</small>}</span>} defaultOpen={defaultOpen}>{children}</Disclosure> : <Panel title={title} action={summary ? <span className="panel-kicker">{summary}</span> : undefined}>{children}</Panel>}</div> }
function CustomerDetail({ accounts, detail, onSelect, onBack }: { accounts: Account[]; detail: Account360; onSelect: (id: string) => void; onBack: () => void }) {
  const [switchQuery, setSwitchQuery] = useState(''); const attractiveness = detail.account_attractiveness; const name = accountName(detail.account); const availableFactors = attractiveness.factors.filter(factor => !factor.missing)
  const switchResults = switchQuery ? accounts.filter(item => `${accountName(item)} ${item.industries.join(' ')}`.toLowerCase().includes(switchQuery.toLowerCase())).slice(0, 6) : []
  const choose = (id: string) => { setSwitchQuery(''); onSelect(id) }
  return <div className="surface account-detail-surface"><div className="account-workspace-navigation"><Button className="account-workspace-back" variant="ghost" onClick={onBack}>← Customers &amp; Prospects</Button><div className="account-switcher"><SearchInput aria-label="Switch Customer" placeholder="Search Customer, industry, or location" value={switchQuery} onChange={event => setSwitchQuery(event.target.value)} />{switchResults.length > 0 && <div className="account-switch-results" role="listbox" aria-label="Customer switcher results">{switchResults.map(item => <button type="button" role="option" aria-selected="false" className="account-row account-switch-result" key={item.id} onClick={() => choose(item.id)}><span><strong>{accountName(item)}</strong><small>{item.industries.join(' / ') || 'Industry unavailable'}</small></span><State value={item.truth_state ?? 'UNAVAILABLE'} /></button>)}</div>}</div></div><section className="account-workspace" aria-label={`${name} Customer workspace`}>
    <header className="account-workspace-header"><div className="account-workspace-heading"><span className="eyebrow">Customers &amp; Prospects / Customer 360</span><h1>{name}</h1><p>{detail.account.industries.join(' · ') || 'Industry unavailable'}</p></div><div className="account-workspace-states"><StatusBadge value={classification(detail.account)} kind="entity" label={classificationLabel(detail.account)} />{detail.account.btx_top_100 && <StatusBadge value="BTX Top 100" />}<State value={detail.truth_categories.public} /><State value={detail.truth_categories.btx} /></div></header>
    <section className="account-decision-zone" aria-label="Customer decision summary"><StatTile label="Attractiveness" value={attractiveness.score ?? 'Unavailable'} detail={humanize(attractiveness.status)} /><StatTile label="Research priority" value={detail.prospect_research_priority ? humanize(detail.prospect_research_priority) : 'Unavailable'} detail="Canonical research priority" /><div className="account-why"><span className="eyebrow">Why this Customer matters</span><p>{detail.reason_for_attention ?? 'No current reason for attention is available.'}</p><strong>Next review</strong><p>{detail.recommended_next_step ?? 'No governed next step is currently available.'}</p></div></section>
    <div className="account-primary-grid"><CustomerSection className="attention-section" title="What needs attention" summary={`${detail.alerts.length} governed alerts`} defaultOpen>{detail.alerts.length ? <div className="card-list">{detail.alerts.map(alert => <div className="workspace-attention" key={alertRenderKey(alert)}><State value={alert.severity} /><strong>{humanize(alert.type)}</strong><p>{alert.trigger_reason}</p><small>{alert.recommended_action}</small></div>)}</div> : <Empty>No governed alert is currently open for this Customer.</Empty>}</CustomerSection><CustomerSection title="Commercial context" summary="SAMPLE"><Notice title="Simulated BTX commercial context">Quotes, ownership, matching, and workflow context are POC simulation—not BTX-connected records.</Notice><div className="workspace-metrics"><span><strong>{detail.prism_commercial_context.length}</strong> commercial records</span><span><strong>{detail.paperless_quotes.length}</strong> quote records</span><span><strong>{detail.matching.length}</strong> matching records</span></div>{detail.paperless_quotes.length ? <div className="card-list">{detail.paperless_quotes.map(quote => <div className="line" key={quote.id}><span><strong>{quote.id}</strong><small>Quoted {quote.quoted_at}</small></span><State value={quote.status} /></div>)}</div> : <Empty>No SAMPLE quote history is available.</Empty>}</CustomerSection></div>
    <div className="account-secondary-grid"><CustomerSection title="Recent intelligence" summary="Public evidence"><Signals items={detail.intelligence} /></CustomerSection><CustomerSection title="Public professional contact research" summary={`${detail.public_contacts.length} records`}>{detail.public_contacts.length ? <div className="evidence-list">{detail.public_contacts.map(contact => <EvidenceSource key={`${contact.contact_type}-${contact.name ?? contact.role_family}`} title={contact.name ?? contact.role_family} source="Public professional research" evidenceState={contact.verification_state} url={contact.source_url} detail={contact.title_or_function ?? contact.role_family} />)}</div> : <Empty>{`No verified public contact is available. Role-family target: ${detail.account.contact_role_families?.join(', ') ?? 'procurement / engineering'}.`}</Empty>}</CustomerSection><CustomerSection title="Public identity & geography" summary={humanize(detail.public_identity_state)}><MetadataRow label="Public relationship" value={humanize(detail.public_relationship?.state ?? 'UNAVAILABLE')} /><p className="workspace-intro">{detail.public_relationship?.basis ?? 'No public relationship basis is currently available.'}</p>{detail.public_facilities.length ? <div className="evidence-list">{detail.public_facilities.map(facility => <EvidenceSource key={facility.id} title={facility.name} source={`${facility.city}, ${facility.region}`} evidenceState={facility.verification_state} url={facility.source_url} detail={facility.facility_type} />)}</div> : <Empty>Public location has not yet been verified for this Customer. No map pin is shown.</Empty>}</CustomerSection><CustomerSection title="Attractiveness rationale & missingness" summary={humanize(attractiveness.status)}><Notice title="Customer Attractiveness · POC simulation">Deterministic canonical simulated BTX-only inputs; this is not an external industry rank.</Notice>{attractiveness.exclusion_reason ? <p className="truth-note">{attractiveness.exclusion_reason}</p> : <div className="factor-list">{attractiveness.factors.map(factor => <div className="factor-row" key={factor.name}><span><strong>{humanize(factor.name)}</strong><small>{factor.missing ? 'Missing canonical input' : `Canonical contribution ${factor.contribution ?? 'Unavailable'}`}</small>{factor.gaps.length > 0 && <small>{factor.gaps.join(', ')}</small>}</span><strong>{factor.score ?? '—'}</strong></div>)}</div>}{!attractiveness.exclusion_reason && availableFactors.length === 0 && <Empty>No canonical score factors are currently available.</Empty>}{attractiveness.missingness.length > 0 ? <Notice tone="warning" title="Missing inputs">{attractiveness.missingness.join(', ')}</Notice> : <MetadataRow label="Input coverage" value={`${Number(attractiveness.coverage) * 100}%`} />}</CustomerSection></div>
    <CustomerSection className="account-workspace-relationship" title="Relationship Intelligence" summary="Canonical connections"><RelationshipIntelligence key={detail.account.id} accountId={detail.account.id} /></CustomerSection>
    <CustomerSection title="Evidence & provenance" summary={humanize(detail.provenance.evidence_state)}><EvidenceSource title="Canonical Customer record" source={detail.provenance.source_record_id} evidenceState={detail.provenance.evidence_state} detail={detail.missingness.length ? `Missingness: ${detail.missingness.join(', ')}` : 'No additional projection missingness reported.'} /></CustomerSection>
  </section></div>
}
