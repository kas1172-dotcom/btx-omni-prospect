import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { Account, Account360, AccountRelationships, OmniContext, RelationshipPath, Signal } from '../../types/api'
import { Empty, Panel, State } from '../../components/UI'
import './accounts.css'

function PortfolioSummary({ label, value, detail }: { label: string; value: number; detail: string }) {
  return <article className="portfolio-summary-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>
}

export function Accounts({ accounts, detail, onSelect, onBack, onOmniContext }: { accounts: Account[]; detail?: Account360; onSelect: (id: string) => void; onBack: () => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void }) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('RICH')
  const [industry, setIndustry] = useState('ALL')
  const industries = [...new Set(accounts.flatMap(item => item.industries))]
  const shown = useMemo(() => accounts.filter(item => (filter === 'RICH' ? item.is_rich_scenario : true) && (industry === 'ALL' || item.industries.includes(industry)) && `${item.name} ${item.industries.join(' ')} ${item.location?.state ?? ''}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => Number(Boolean(b.is_rich_scenario)) - Number(Boolean(a.is_rich_scenario))), [accounts, filter, industry, query])
  const activeFilters = useMemo(() => ({ ...(filter === 'RICH' ? { account_scope: 'RICH' } : {}), ...(industry === 'ALL' ? {} : { market: industry }) }), [filter, industry])
  const visibleRecordIds = useMemo(() => shown.slice(0, 50).map(account => account.id), [shown])
  const scoredCount = useMemo(() => shown.filter(account => account.attractiveness !== null && account.attractiveness !== undefined).length, [shown])
  const selectAccount = (id: string) => { setQuery(''); onSelect(id) }

  useEffect(() => { onOmniContext({ active_filters: Object.keys(activeFilters).length ? activeFilters : undefined, visible_record_ids: visibleRecordIds }) }, [activeFilters, onOmniContext, visibleRecordIds])
  useEffect(() => () => onOmniContext({}), [onOmniContext])

  if (detail) return <div className="surface account-detail-surface"><div className="account-workspace-navigation"><button className="account-workspace-back" onClick={onBack}>← Account portfolio</button><div className="account-switcher"><input placeholder="Search company, industry, or location" value={query} onChange={event => setQuery(event.target.value)} aria-label="Switch account" />{query && <div className="account-switch-results">{shown.slice(0, 6).map(item => <button className="account-row account-switch-result" key={item.id} onClick={() => selectAccount(item.id)}><span><strong>{item.name}</strong><small>{item.industries.join(' / ') || 'Industry unavailable'}</small></span><State value={item.truth_state ?? 'UNAVAILABLE'} /></button>)}</div>}</div></div><AccountDetail detail={detail} /></div>

  return <div className="surface accounts-surface"><div className="page-title accounts-title"><span className="eyebrow">Curated public-company scenarios</span><h1>Accounts</h1><p>Every account is a researched public company. Start with the curated scenarios or browse the full researched universe.</p></div><div className="portfolio-summary-grid" aria-label="Account portfolio summary"><PortfolioSummary label="Current portfolio" value={shown.length} detail="Canonical accounts in the current view" /><PortfolioSummary label="Curated scenarios" value={shown.filter(account => account.is_rich_scenario).length} detail="Seller-scenario accounts in this view" /><PortfolioSummary label="Scores available" value={scoredCount} detail="Canonical Account Attractiveness outputs" /></div><div className={`account-layout ${detail ? 'account-layout-detail' : 'account-layout-portfolio'}`}><Panel title="Account portfolio" action={<span className="panel-kicker">{shown.length} companies · current canonical order</span>}><div className="portfolio-controls"><div className="filters"><input placeholder="Search company, industry, or location" value={query} onChange={event => setQuery(event.target.value)} /><select aria-label="Account scope" value={filter} onChange={event => setFilter(event.target.value)}><option value="RICH">Curated scenarios</option><option value="ALL">All researched companies</option></select></div><div className="chips filter-chips" aria-label="Industry filters"><button className={industry === 'ALL' ? 'selected' : ''} onClick={() => setIndustry('ALL')}>All industries</button>{industries.map(value => <button className={industry === value ? 'selected' : ''} key={value} onClick={() => setIndustry(value)}>{value}</button>)}</div></div><div className="portfolio-column-headings" aria-hidden="true"><span>Account</span><span>Attractiveness</span><span>Evidence state</span></div><div className="account-list portfolio-list">{shown.map(item => <button className="account-row portfolio-row" key={item.id} onClick={() => selectAccount(item.id)}><span className="portfolio-account"><strong>{item.name}</strong><small>{item.industries.join(' / ') || 'Industry unavailable'}{item.location?.city && item.location?.state ? ` · ${item.location.city}, ${item.location.state}` : ''}</small><small>{item.prospect_rationale ?? 'No additional research rationale is available.'}</small></span><span className="portfolio-score"><small>Account Attractiveness</small><strong>{item.attractiveness ?? '—'}</strong></span><State value={item.truth_state ?? 'UNAVAILABLE'} /></button>)}</div></Panel>{detail && <AccountDetail detail={detail} />}</div></div>
}

function Signals({ items }: { items: Signal[] }) { return items.length ? <div className="card-list">{items.map(item => <div className="line" key={item.id}><span><strong>{item.title}</strong><small>{item.evidence_state} · publicly curated evidence</small></span><a href={item.source_url} target="_blank" rel="noreferrer">Source</a></div>)}</div> : <Empty>No curated public event is available.</Empty> }

const humanize = (value: string) => value.replaceAll('_', ' ')

function RelationshipPathRow({ path }: { path: RelationshipPath }) {
  const hop = path.hops[0]
  const provenance = hop?.provenance
  const sourceReference = provenance?.source_record_id ?? hop?.source_ids?.[0]

  return <article className="relationship-path-row">
    <div className="relationship-path-heading">
      <span className="relationship-path-kind">{path.target_entity.kind}</span>
      <strong>{path.target_entity.name}</strong>
      <div className="relationship-path-states"><State value={path.presentation_state} /><State value={path.overall_evidence_state} /></div>
    </div>
    {hop && <p className="relationship-path-direction">{path.source_entity.name} <span>→</span> {humanize(hop.relationship_type)} <span>→</span> {path.target_entity.name}</p>}
    {path.narrative && <p className="relationship-path-narrative">{path.narrative}</p>}
    <div className="relationship-path-provenance">
      <span>{provenance?.classification === 'INTERNAL_COMMERCIAL' ? 'SAMPLE internal commercial context' : 'Canonical relationship evidence'}</span>
      {sourceReference && <small>Record: {sourceReference}</small>}
      {provenance?.source_url && <a href={provenance.source_url} target="_blank" rel="noreferrer">Source</a>}
    </div>
  </article>
}

function RelationshipPathChain({ path }: { path: RelationshipPath }) {
  return <article className="relationship-chain">
    <div className="relationship-chain-heading">
      <span className="relationship-path-kind">Canonical {path.hops.length}-hop path</span>
      <strong>{path.source_entity.name} <span>→</span> {path.target_entity.name}</strong>
    </div>
    <ol className="relationship-chain-hops">
      {path.hops.map((hop, index) => {
        const sourceReference = hop.provenance?.source_record_id ?? hop.source_ids?.[0]
        const evidenceLabel = hop.provenance?.classification === 'INTERNAL_COMMERCIAL' ? 'SAMPLE internal commercial evidence' : 'Public/canonical relationship evidence'
        return <li key={`${path.path_id}:${index}`} className="relationship-chain-hop">
          <div className="relationship-chain-hop-direction"><strong>{hop.from_entity.name}</strong><span>→</span><em>{humanize(hop.relationship_type)}</em><span>→</span><strong>{hop.to_entity.name}</strong></div>
          <div className="relationship-chain-hop-meta"><span>{hop.from_entity.kind} → {hop.to_entity.kind}</span><State value={hop.presentation_state} /><State value={hop.evidence_state} /></div>
          <div className="relationship-path-provenance"><span>{evidenceLabel}</span>{sourceReference && <small>Record: {sourceReference}</small>}{hop.provenance?.source_url && <a href={hop.provenance.source_url} target="_blank" rel="noreferrer">Source</a>}</div>
        </li>
      })}
    </ol>
  </article>
}

function RelationshipIntelligence({ accountId }: { accountId: string }) {
  const [relationships, setRelationships] = useState<AccountRelationships>()
  const [error, setError] = useState(false)
  const [view, setView] = useState<'direct' | 'paths'>('direct')

  useEffect(() => {
    let active = true
    void api.relationships(accountId).then(result => {
      if (active) setRelationships(result)
    }).catch(() => {
      if (active) setError(true)
    })
    return () => { active = false }
  }, [accountId])

  const directPaths = relationships?.direct_relationships.slice(0, 8) ?? []
  const multiHopPaths = relationships?.paths.filter(path => path.hops.length > 1).slice(0, 6) ?? []
  return <Panel title="Relationship Intelligence" action={<span className="panel-kicker">READ ONLY · canonical paths</span>}>
    <p className="workspace-intro relationship-intelligence-intro">Only canonical relationship records are shown. Public professional-contact research remains separate and does not establish a relationship path or introduction.</p>
    <div className="relationship-view-toggle" role="tablist" aria-label="Relationship Intelligence view">
      <button role="tab" aria-selected={view === 'direct'} className={view === 'direct' ? 'selected' : ''} onClick={() => setView('direct')}>Direct relationships</button>
      <button role="tab" aria-selected={view === 'paths'} className={view === 'paths' ? 'selected' : ''} onClick={() => setView('paths')}>Relationship paths</button>
    </div>
    {!relationships && !error && <p className="relationship-intelligence-loading">Loading canonical relationship records…</p>}
    {error && <Empty>Canonical relationship records could not be loaded for this account. No relationship conclusion is shown.</Empty>}
    {relationships && view === 'direct' && directPaths.length === 0 && <Empty>No canonical direct relationship records are available for this account. This does not establish a real-world absence.</Empty>}
    {view === 'direct' && directPaths.length > 0 && <div className="relationship-path-list">{directPaths.map(path => <RelationshipPathRow key={path.path_id} path={path} />)}</div>}
    {relationships && view === 'direct' && relationships.direct_relationships.length > directPaths.length && <p className="relationship-intelligence-bound">Showing the first {directPaths.length} of {relationships.direct_relationships.length} direct canonical paths. This view does not infer additional paths.</p>}
    {relationships && view === 'paths' && multiHopPaths.length === 0 && <Empty>No canonical multi-hop relationship paths are available for this account. This does not establish a real-world absence.</Empty>}
    {view === 'paths' && multiHopPaths.length > 0 && <div className="relationship-chain-list">{multiHopPaths.map(path => <RelationshipPathChain key={path.path_id} path={path} />)}</div>}
    {relationships && view === 'paths' && relationships.paths.filter(path => path.hops.length > 1).length > multiHopPaths.length && <p className="relationship-intelligence-bound">Showing the first {multiHopPaths.length} canonical multi-hop paths returned by the service. This view does not infer additional paths.</p>}
  </Panel>
}

function AccountDetail({ detail }: { detail?: Account360 }) {
  if (!detail) return <Panel title="Account 360"><Empty>Select a company to view public evidence, simulated BTX context, and uncertainty.</Empty></Panel>

  const score = detail.account_attractiveness
  const name = detail.account.name ?? detail.account.legal_name ?? detail.account.id
  const availableFactors = score.factors.filter(factor => !factor.missing)

  return <section className="account-workspace" aria-label={`${name} account workspace`}>
    <header className="account-workspace-header">
      <div className="account-workspace-heading"><span className="eyebrow">Accounts / Account 360 workspace</span><h2>{name}<small> / Account 360</small></h2><p>{detail.account.industries.join(' · ') || 'Industry unavailable'} · Public research and governed SAMPLE commercial context</p></div>
      <div className="account-workspace-states"><State value={detail.truth_categories.public} /><State value={detail.truth_categories.btx} /></div>
    </header>

    <section className="account-decision-zone" aria-label="Account decision support">
      <div className="account-score-summary"><span>Account Attractiveness</span><strong>{score.score ?? '—'}</strong><State value={score.status} /></div>
      <div><span className="eyebrow">Why it matters</span><p>{detail.reason_for_attention ?? 'No current reason for attention is available.'}</p></div>
      <div><span className="eyebrow">Recommended review</span><p>{detail.recommended_next_step ?? 'No governed next step is currently available.'}</p></div>
    </section>

    <div className="account-workspace-grid">
      <Panel title="Public evidence & geography" action={<State value={detail.public_identity_state} />}>
        <div className="workspace-fact"><span>Public relationship</span><strong>{detail.public_relationship?.state ?? 'UNAVAILABLE'}</strong><small>{detail.public_relationship?.basis ?? 'No public relationship basis is currently available.'}</small></div>
        {detail.public_facilities.length > 0 ? <div className="card-list">{detail.public_facilities.map(facility => <div className="line" key={facility.id}><span><strong>{facility.name}</strong><small>{facility.city}, {facility.region} · {facility.verification_state}</small></span>{facility.source_url && <a href={facility.source_url} target="_blank" rel="noreferrer">Source</a>}</div>)}</div> : <Empty>Public location has not yet been verified for this company. No map pin is shown.</Empty>}
      </Panel>

      <Panel title="Public professional contact research" action={<span className="panel-kicker">{detail.public_contacts.length} public records</span>}>
        <p className="workspace-intro">Only legitimate public professional contacts and channels are shown.</p>
        {detail.public_contacts.length ? <div className="card-list">{detail.public_contacts.map(contact => <div className="line" key={`${contact.contact_type}-${contact.name}`}><span><strong>{contact.name ?? contact.role_family}</strong><small>{contact.title_or_function ?? contact.role_family} · {contact.verification_state}</small></span>{contact.source_url && <a href={contact.source_url} target="_blank" rel="noreferrer">Source</a>}</div>)}</div> : <Empty>{`Role-family target: ${detail.account.contact_role_families?.join(', ') ?? 'procurement / engineering'}`}</Empty>}
      </Panel>

      <Panel title="Commercial position" action={<State value="SAMPLE" />}>
        <p className="workspace-intro"><strong>Simulated BTX commercial context.</strong> Quotes, matching, ownership, and workflow context are POC simulation—not BTX-connected records.</p>
        <div className="workspace-metrics"><span><strong>{detail.prism_commercial_context.length}</strong> commercial context records</span><span><strong>{detail.paperless_quotes.length}</strong> quote records</span><span><strong>{detail.matching.length}</strong> matching records</span></div>
        {detail.paperless_quotes.length ? <div className="card-list">{detail.paperless_quotes.map(quote => <div className="line" key={quote.id}><span><strong>{quote.id}</strong><small>Quoted {quote.quoted_at}</small></span><State value={quote.status} /></div>)}</div> : <Empty>No SAMPLE quote history is available.</Empty>}
      </Panel>

      <Panel title="What needs attention" action={<span className="panel-kicker">{detail.alerts.length} governed alerts</span>}>
        {detail.alerts.length ? <div className="card-list">{detail.alerts.map(alert => <div className="workspace-attention" key={alert.id}><State value={alert.severity} /><strong>{humanize(alert.type)}</strong><p>{alert.trigger_reason}</p><small>{alert.recommended_action}</small></div>)}</div> : <Empty>No governed alert is currently open for this account.</Empty>}
      </Panel>
    </div>

    <div className="account-workspace-lower">
      <Panel title="Signals, health & rationale" action={<span className="panel-kicker">Public intelligence</span>}>
        <div className="workspace-rationale"><span className="eyebrow">Why this account is advancing</span><p>{detail.prospect_rationale ?? detail.reason_for_attention ?? 'No research rationale is currently available.'}</p></div>
        <Signals items={detail.intelligence} />
      </Panel>

      <Panel title="Attractiveness rationale" action={<State value={score.status} />}>
        <p className="workspace-intro"><strong>Account Attractiveness · POC simulation</strong> · Coverage {Number(score.coverage) * 100}% · canonical simulated BTX-only scoring; external industry rank is separate.</p>
        {score.exclusion_reason ? <p className="truth-note">{score.exclusion_reason}</p> : <div className="factor-list">{score.factors.map(factor => <div className="factor-row" key={factor.name}><span><strong>{humanize(factor.name)}</strong><small>{factor.missing ? 'Missing canonical input' : `Canonical contribution ${factor.contribution ?? '—'}`}</small>{factor.gaps.length > 0 && <small>{factor.gaps.join(', ')}</small>}</span><strong>{factor.score ?? '—'}</strong></div>)}</div>}
        {!score.exclusion_reason && availableFactors.length === 0 && <Empty>No canonical score factors are currently available.</Empty>}
        {score.missingness.length > 0 && <p className="truth-note">Missingness: {score.missingness.join(', ')}</p>}
      </Panel>
    </div>

    <div className="account-workspace-relationship">
      <RelationshipIntelligence key={detail.account.id} accountId={detail.account.id} />
    </div>
  </section>
}
