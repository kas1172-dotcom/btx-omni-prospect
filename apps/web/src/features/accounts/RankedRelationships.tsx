import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { api } from '../../api/client'
import type { CanonicalGraphEdge, CanonicalGraphNode, RankedRelationships as Result, RankedRoute, RelationshipMode } from '../../types/relationships'
import './ranked-relationships.css'
import { CommercialEvidence } from './CommercialEvidence'
import type { OmniContext } from '../../types/api'
import { SupportingEvidence } from '../../components/SupportingEvidence'
import { presentationLabel } from '../../components/presentation'
import { relationshipDirectionLabel, relationshipEvidenceLabel, relationshipPredicateLabel, relationshipRouteStatus } from '../../components/relationshipPresentation'
import { LoadingStatus } from '../../components/UI'

const modes: Array<[RelationshipMode, string]> = [['cross_account_experience', 'Shared experience'], ['commercial_fit', 'Commercial fit'], ['contact_candidates', 'Contact candidates'], ['documented_access', 'Documented access']]
const label = (value: string) => presentationLabel(value, 'relationship')
type Point = { x: number; y: number }
type VisualRelation = 'commercial' | 'people' | 'technical' | 'facility' | 'risk' | 'context'

const nodeSymbols: Record<string, string> = { account: 'CO', business_unit: 'BU', facility: 'FX', person: 'PR', role: 'RL', program: 'PG', component: 'CP', component_class: 'CP', capability: 'CA', certification: 'QC', public_event: 'IN', opportunity: 'OP' }
const relationClass = (predicate: string): VisualRelation => {
  const value = predicate.toLocaleLowerCase()
  if (/risk|delay|issue|cancel|constraint/.test(value)) return 'risk'
  if (/person|role|employ|contact|introduc/.test(value)) return 'people'
  if (/facility|site|location|geograph|proximity/.test(value)) return 'facility'
  if (/program|component|capabil|certif|platform|part/.test(value)) return 'technical'
  if (/rfq|quote|order|ship|commercial|customer|supplier|award|work/.test(value)) return 'commercial'
  return 'context'
}
const evidenceClass = (truthClass: string) => /hypothesis|unresolved/i.test(truthClass) ? 'hypothesis' : /infer|candidate|requires_validation/i.test(truthClass) ? 'inferred' : 'recorded'
const stableNumber = (value: string) => [...value].reduce((total, character) => ((total * 31) + character.charCodeAt(0)) >>> 0, 2166136261)

function graphDepths(nodes: CanonicalGraphNode[], edges: CanonicalGraphEdge[], selected?: RankedRoute) {
  const depths = new Map<string, number>()
  selected?.node_ids.forEach((id, index) => depths.set(id, index))
  const origin = selected?.node_ids[0] ?? nodes[0]?.id
  if (!origin) return depths
  depths.set(origin, 0)
  const adjacency = new Map<string, string[]>()
  edges.forEach(edge => { adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), edge.target]); adjacency.set(edge.target, [...(adjacency.get(edge.target) ?? []), edge.source]) })
  const queue = [origin]
  while (queue.length) {
    const current = queue.shift() as string
    const nextDepth = (depths.get(current) ?? 0) + 1
    for (const adjacent of adjacency.get(current) ?? []) if (!depths.has(adjacent)) { depths.set(adjacent, nextDepth); queue.push(adjacent) }
  }
  return depths
}

function initialGraphPositions(result: Result, selected: RankedRoute | undefined, mobile: boolean, previous: Map<string, Point>) {
  const positions = new Map(previous)
  const depths = graphDepths(result.graph.nodes, result.graph.edges, selected)
  if (mobile) {
    selected?.node_ids.forEach((id, index) => { if (!positions.has(id)) positions.set(id, { x: 155, y: 95 + index * 172 }) })
    result.graph.nodes.filter(node => !positions.has(node.id)).toSorted((a, b) => a.id.localeCompare(b.id)).forEach((node, index) => positions.set(node.id, { x: 155, y: 95 + ((selected?.node_ids.length ?? 0) + index) * 172 }))
    return positions
  }
  const center = { x: 220, y: 390 }
  selected?.node_ids.forEach((id, index) => {
    if (positions.has(id)) return
    if (index === 0) { positions.set(id, center); return }
    const radius = Math.min(560, 60 + index * 160)
    const angle = -.34 + index * .08
    positions.set(id, { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius })
  })
  const contextByDepth = new Map<number, CanonicalGraphNode[]>()
  result.graph.nodes.filter(node => !positions.has(node.id)).forEach(node => { const depth = Math.min(6, Math.max(1, depths.get(node.id) ?? 2)); contextByDepth.set(depth, [...(contextByDepth.get(depth) ?? []), node]) })
  contextByDepth.forEach((nodesAtDepth, depth) => nodesAtDepth.toSorted((a, b) => a.id.localeCompare(b.id)).forEach((node, index) => {
    const radius = Math.min(560, 60 + depth * 160)
    let angle = -1.28 + (2.56 * (index + 1) / (nodesAtDepth.length + 1)) + ((stableNumber(node.id) % 12) / 100)
    let point = { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius }
    for (let attempts = 0; attempts < 16 && [...positions.values()].some(other => Math.hypot(other.x - point.x, other.y - point.y) < 205); attempts++) { angle = Math.min(1.42, angle + .17); point = { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius } }
    positions.set(node.id, point)
  }))
  return positions
}

export function RankedRelationships({ accountId, initialMode, initialPathId, onSelection, onOmniContext }: { accountId: string; initialMode?: string; initialPathId?: string; onSelection?: (pathId: string | undefined, mode: RelationshipMode) => void; onOmniContext: (context: Pick<OmniContext, 'relationship_selection'>) => void }) {
  const [mode, setMode] = useState<RelationshipMode>(() => modes.some(([value]) => value === initialMode) ? initialMode as RelationshipMode : 'cross_account_experience')
  const [depth, setDepth] = useState(4)
  const [component, setComponent] = useState('')
  const [target, setTarget] = useState('')
  const [targetComponent, setTargetComponent] = useState('')
  const [result, setResult] = useState<Result>()
  const [pending, setPending] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [selectedId, setSelectedId] = useState<string | undefined>(initialPathId)
  const [selectedEdge, setSelectedEdge] = useState<string>()
  const [hoveredRoute, setHoveredRoute] = useState<string>()
  const [evidenceId, setEvidenceId] = useState('')
  const [selectedNode, setSelectedNode] = useState<string>()
  const [focusHistory, setFocusHistory] = useState<string[]>([])
  const [showGraph, setShowGraph] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [expanded, setExpanded] = useState(true)
  const [expansions, setExpansions] = useState<string[]>([])
  const [contextPage, setContextPage] = useState(0)
  const [revisionGuard, setRevisionGuard] = useState<string>()
  const [budgetLevel, setBudgetLevel] = useState(0)
  const [includeRecords, setIncludeRecords] = useState(false)
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches)
  const [layout, setLayout] = useState<{ key: string; positions: Map<string, Point> }>({ key: '', positions: new Map() })
  const stageRef = useRef<HTMLDivElement>(null)
  useEffect(() => { const media = window.matchMedia('(max-width: 760px)'); const update = () => { setMobile(media.matches); setContextPage(0); setPending(true) }; media.addEventListener('change', update); return () => media.removeEventListener('change', update) }, [])
  useEffect(() => {
    const controller = new AbortController()
    void api.rankedRelationships({ source_account_id: accountId, mode, depth, source_component_id: component || undefined, target_component_id: mode === 'cross_account_experience' ? targetComponent || undefined : undefined, target_account_id: mode === 'cross_account_experience' ? target || undefined : undefined, selected_path_id: selectedId, node_budget: (mobile ? [12, 24, 48] : [24, 48, 80])[budgetLevel], edge_budget: (mobile ? [20, 40, 80] : [40, 80, 160])[budgetLevel], expanded_node_ids: expansions, context_page: contextPage, expected_graph_revision: revisionGuard, include_record_context: includeRecords }, controller.signal).then(value => {
      if (!controller.signal.aborted) {
        const valueRoutes = value.evaluated_routes ?? []
        const valueSelected = valueRoutes.find(route => route.path_id === selectedId) ?? valueRoutes.find(route => route.path_id === value.graph.selected_path_id) ?? valueRoutes[0]
        const valueLayoutKey = JSON.stringify([accountId, value.mode, value.scope?.target_ids, value.scope?.source_component_id, value.scope?.target_component_id, mobile])
        setLayout(current => ({ key: valueLayoutKey, positions: initialGraphPositions(value, valueSelected, mobile, current.key === valueLayoutKey ? current.positions : new Map()) }))
        setResult(value); setPending(false); setError('')
      }
    }).catch(() => { if (!controller.signal.aborted) { setError('Connections could not be refreshed. Retry to obtain a current result.'); setPending(false) } })
    return () => controller.abort()
  }, [accountId, mode, depth, retry, component, target, targetComponent, selectedId, mobile, expansions, contextPage, revisionGuard, budgetLevel, includeRecords])
  const routes = useMemo(() => result?.evaluated_routes ?? [], [result?.evaluated_routes])
  const selected = routes.find(r => r.path_id === selectedId) ?? routes.find(r => r.path_id === result?.graph.selected_path_id) ?? routes[0]
  useLayoutEffect(() => {
    onOmniContext({ relationship_selection: selected && result?.scope && result.eligible_graph_revision && !pending && !error ? {
      source_account_id: accountId, target_ids: result.scope.target_ids, mode: result.mode, as_of: result.scope.as_of,
      depth: result.searched_depth, path_id: selected.path_id, graph_revision: result.eligible_graph_revision,
      source_component_id: result.scope.source_component_id, target_component_id: result.scope.target_component_id,
    } : undefined })
  }, [accountId, selected, result, pending, error, onOmniContext])
  useEffect(() => () => onOmniContext({ relationship_selection: undefined }), [onOmniContext])
  const layoutKey = JSON.stringify([accountId, result?.mode, result?.scope?.target_ids, result?.scope?.source_component_id, result?.scope?.target_component_id, mobile])
  const positions = new Map([...layout.positions].filter(([id]) => result?.graph.nodes.some(n => n.id === id) && (expanded || selected?.node_ids.includes(id))))
  const stageHeight = mobile ? Math.max(520, ...[...positions.values()].map(p => p.y + 90)) : 780
  const stageWidth = mobile ? 310 : 1200
  const edge = result?.graph.edges.find(e => e.id === selectedEdge)
  const node = result?.graph.nodes.find(n => n.id === selectedNode)
  const visibleDepths = useMemo(() => result ? graphDepths(result.graph.nodes, result.graph.edges, selected) : new Map<string, number>(), [result, selected])
  const highlightedEdgeIds = useMemo(() => new Set((routes.find(route => route.path_id === hoveredRoute) ?? selected)?.edge_ids ?? []), [hoveredRoute, routes, selected])
  const relatedIntelligence = result?.related_intelligence?.find(item => item.assessment.priority_eligible) ?? result?.related_intelligence?.[0]
  const changing = (nextMode: RelationshipMode, nextDepth: number) => { setPending(true); setError(''); setSelectedId(undefined); setSelectedEdge(undefined); setSelectedNode(undefined); setExpansions([]); setContextPage(0); setRevisionGuard(undefined); setMode(nextMode); setDepth(nextDepth); onSelection?.(undefined, nextMode) }
  const selectRoute = (id: string) => { if (id === selectedId && contextPage === 0) return; setPending(true); setSelectedId(id); setSelectedEdge(undefined); setContextPage(0); setRevisionGuard(result?.eligible_graph_revision); onSelection?.(id, mode) }
  const pageContext = (page: number) => { setPending(true); setContextPage(page); setSelectedId(selected?.path_id); setRevisionGuard(result?.eligible_graph_revision) }
  const toggleExpansion = (id: string) => { setPending(true); setExpansions(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]); setContextPage(0); setSelectedId(selected?.path_id); setRevisionGuard(result?.eligible_graph_revision); setExpanded(true) }
  const focusNode = (id: string) => { if (selectedNode && id !== selectedNode) setFocusHistory(history => [...history.slice(-19), selectedNode]); setSelectedNode(id) }
  return <section className="ranked-relationships" aria-label="Ranked canonical relationships" aria-busy={pending}>
    <label><input type="checkbox" checked={includeRecords} disabled={pending || !['commercial_fit', 'cross_account_experience'].includes(mode)} onChange={event => {
      setIncludeRecords(event.target.checked); setPending(true); setContextPage(0); setExpansions([]);
      setSelectedId(selected?.path_id); setRevisionGuard(result?.eligible_graph_revision);
    }} /> Show linked commercial records as context</label>
    {includeRecords && <p>Record links explain the commercial history. They do not strengthen a route, establish personal access or promise capacity.</p>}
    <div className="ranked-toolbar"><label>Objective<select value={mode} onChange={e => changing(e.target.value as RelationshipMode, depth)}>{modes.map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></label><label>Search depth<select value={depth} onChange={e => changing(mode, Number(e.target.value))}><option value={4}>Up to four edges</option><option value={6}>Deeper · up to six edges</option></select></label><button onClick={() => { changing(mode, depth); setRetry(n => n + 1) }}>Refresh evidence</button></div>
    {result?.query_options && <div className="ranked-toolbar"><label>Component scope<select value={component} onChange={e => { changing(mode, depth); setComponent(e.target.value) }}><option value="">All applicable components</option>{result.query_options.components.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}</select></label>{mode === 'cross_account_experience' && <label>Compare account<select value={target} onChange={e => { changing(mode, depth); setTarget(e.target.value); setTargetComponent('') }}><option value="">Relevant shared experience</option>{result.query_options.accounts.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}</select></label>}{mode === 'cross_account_experience' && target && <label>Compared component<select value={targetComponent} onChange={e => { changing(mode, depth); setTargetComponent(e.target.value) }}><option value="">All compared components</option>{result.query_options.target_components?.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}</select></label>}</div>}
    {pending && <LoadingStatus>Updating connections… Previous results remain visible but are not current.</LoadingStatus>}
    {error && <p role="alert">{error}</p>}
    {result && <p>{result.candidate_count} paths found · searched up to {result.searched_depth} edges{!result.search_complete ? ` · Partial search: ${label(result.stop_reason ?? 'budget reached')}` : ''}</p>}
    {result?.scope && <p>Evidence evaluated as of {result.scope.as_of}. Commercial history through {result.commercial_as_of?.join(', ') ?? 'the recorded snapshot'}.</p>}
    {result?.temporal_limits && Object.values(result.temporal_limits).some(value => value.undated_plans_excluded_from_historical_query > 0) && <details><summary>Historical query limits</summary><p>Undated recovery proposals were excluded because their historical effective date is unknown. Their authorship and proposed dispatch dates do not establish when a buyer agreed to them.</p></details>}
    {result?.reason && <p>{result.reason}</p>}
    {result && Object.entries(result.groups).map(([status, group]) => group.routes.length > 0 && <div key={status}><h3>{relationshipRouteStatus(status)}</h3><div className="ranked-route-cards">{group.routes.map(route => <button key={route.path_id} aria-pressed={selected?.path_id === route.path_id} disabled={pending || !!error} onClick={() => selectRoute(route.path_id)}><strong>{route.steps.at(-1)?.label}</strong><span>{route.hop_count} recorded connections · {route.factors.bottleneck >= 2 ? 'Historical experience' : 'Possible route to investigate'}</span><span>{route.next_action}</span></button>)}</div></div>)}
    {result?.research_candidates.length ? <details><summary>Research candidates · not recommended connections</summary>{result.research_candidates.map(route => <button key={route.path_id} disabled={pending || !!error} onClick={() => selectRoute(route.path_id)}>{route.steps.at(-1)?.label} · {route.hop_count} edges</button>)}</details> : null}
    {selected && <>
      <h3>Selected route · {selected.hop_count} actual edges</h3>
      <p>{selected.component_context?.map(c => c.label).join(' ↔ ')}</p>
      <ol className="ranked-route-steps">{selected.steps.map((step, index) => <li key={step.id}><strong>{step.label}</strong>{index < selected.edge_ids.length && <button disabled={pending || !!error} onClick={() => setSelectedEdge(selected.edge_ids[index])}>{relationshipPredicateLabel(selected.assertions?.[index]?.predicate)} · {relationshipDirectionLabel(selected.inverse_steps[index])} · step {index + 1}</button>}</li>)}</ol>
      <p><strong>Next action:</strong> {selected.next_action}</p>
      {selected.constraints.map(c => <p key={c.id}><strong>Constraint:</strong> {c.reason}</p>)}
      <details><summary>Why this route · factors and evidence</summary><p>Route strength {Number(selected.utility).toFixed(1)} out of 100; it is not a probability, PWIN or capacity promise.</p>{selected.factor_reasons.map(f => <p key={f.edge_id}>{f.reason} · {relationshipEvidenceLabel(f.truth_class)}</p>)}<p>{selected.evidence_ids.length} supporting record{selected.evidence_ids.length === 1 ? '' : 's'}.</p><details><summary>Technical calculation receipt</summary><small>{result?.rubric_version} · path {selected.path_id}</small></details></details>
      <button className="ranked-graph-toggle" aria-expanded={showGraph} onClick={() => setShowGraph(value => !value)}>{showGraph ? 'Hide network' : 'Explore network'}</button>
      <div className="ranked-network-layout"><div className={`ranked-network ${showGraph ? 'is-open' : ''}`}><header className="ranked-network-head"><div><span className="eyebrow">Relationship field</span><h3>{selected.steps[0]?.label} to {selected.steps.at(-1)?.label}</h3></div><div className="ranked-network-metrics"><span>{selected.hop_count} hops</span><span>{Number(selected.utility).toFixed(1)} route strength</span></div></header>
        <ol className="ranked-route-breadcrumb" aria-label="Selected relationship route">{selected.steps.map((step, index) => <li key={step.id}><span>{index}</span>{step.label}</li>)}</ol>
        <div className="ranked-network-controls"><button onClick={() => setZoom(value => Math.min(2, value + .2))} aria-label="Zoom in">+</button><button onClick={() => setZoom(value => Math.max(.6, value - .2))} aria-label="Zoom out">−</button><button onClick={() => setZoom(1)}>Reset zoom</button><button aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? 'Collapse context' : `Expand context · ${Math.max(0, (result?.graph.nodes.length ?? 0) - selected.node_ids.length)} nodes`}</button><span>Arrows show the recorded direction. Shared entities remain one node.</span></div>
        <p>{result?.graph.nodes.length} visible entities / {result?.graph.edges.length} relationships · {result?.graph.hidden_context_edges ?? 0} additional contextual relationships. Context does not become a recommendation.</p>
        <button disabled={pending || !!error || budgetLevel >= 2} onClick={() => { setPending(true); setBudgetLevel(value => Math.min(2, value + 1)); setContextPage(0); setSelectedId(selected?.path_id); setRevisionGuard(result?.eligible_graph_revision); setExpanded(true) }}>Increase context budget</button>
        <div className="ranked-network-controls" role="group" aria-label="Pan network without dragging"><button onClick={() => stageRef.current?.scrollBy({ left: -240 })}>Pan left</button><button onClick={() => stageRef.current?.scrollBy({ left: 240 })}>Pan right</button><button onClick={() => stageRef.current?.scrollBy({ top: -240 })}>Pan up</button><button onClick={() => stageRef.current?.scrollBy({ top: 240 })}>Pan down</button></div>
        <div className="ranked-graph-legend" aria-label="Relationship graph legend"><span><i className="legend-line selected" />Selected route</span><span><i className="legend-line recorded" />Recorded</span><span><i className="legend-line inferred" />Needs validation</span><span><i className="legend-line hypothesis" />Research hypothesis</span></div>
        <p className="ranked-direction-legend">Color identifies relationship type; line weight reflects the selected route's recorded strength; pattern identifies evidence state. Arrowheads show the recorded direction.</p>
        {result?.graph.context_complete === false && <p role="status">Partial context: {label(result.graph.context_stop_reason ?? 'budget reached')}. Route-search completeness is reported separately.</p>}
        <div className="ranked-network-controls"><button disabled={pending || !!error || contextPage === 0} onClick={() => pageContext(contextPage - 1)}>Previous context page</button><span>Context page {contextPage + 1} of {result?.graph.page_count ?? 1}</span><button disabled={pending || !!error || contextPage + 1 >= (result?.graph.page_count ?? 1)} onClick={() => pageContext(contextPage + 1)}>Next context page</button><button disabled={!focusHistory.length} onClick={() => { setSelectedNode(focusHistory.at(-1)); setFocusHistory(history => history.slice(0, -1)) }}>Back focus</button></div>
        <button onClick={() => { if (result) setLayout({ key: layoutKey, positions: initialGraphPositions(result, selected, mobile, new Map()) }); setExpanded(false); setZoom(mobile ? Math.max(.6, Math.min(1, 620 / (180 + (selected.node_ids.length - 1) * 180))) : 1) }}>Fit selected route</button>
        <div ref={stageRef} className="ranked-stage" tabIndex={0} aria-label="Scrollable relationship network; arrow keys scroll"><svg width={stageWidth * zoom} height={stageHeight * zoom} viewBox={`0 0 ${stageWidth} ${stageHeight}`} role="group" aria-label="Canonical relationship network"><defs><marker id={`route-arrow-${accountId}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker><radialGradient id={`origin-halo-${accountId}`}><stop offset="0" stopColor="#36c5f0" stopOpacity=".18" /><stop offset="1" stopColor="#36c5f0" stopOpacity="0" /></radialGradient></defs>
          {!mobile && <g className="ranked-depth-field" aria-hidden="true"><circle className="origin-halo" cx="220" cy="390" r="145" fill={`url(#origin-halo-${accountId})`} />{Array.from({ length: Math.min(6, Math.max(1, selected.hop_count)) }, (_, index) => { const radius = Math.min(560, 220 + index * 160); return <g key={`${radius}:${index}`}><circle cx="220" cy="390" r={radius} /><text x={220 + radius - 48} y="382">Hop {index + 1}</text></g> })}</g>}
          {result?.graph.edges.map(item => {
            const a = positions.get(item.source); const b = positions.get(item.target); if (!a || !b) return null
            const parallel = result.graph.edges.filter(e => [item.source, item.target].includes(e.source) && [item.source, item.target].includes(e.target)).sort((x, y) => x.id.localeCompare(y.id))
            const offset = (parallel.findIndex(e => e.id === item.id) - (parallel.length - 1) / 2) * 28
            const dx = b.x - a.x; const dy = b.y - a.y; const trim = 1 / Math.max(Math.abs(dx) / 106, Math.abs(dy) / 76)
            const curve = `M${a.x + dx * trim},${a.y + dy * trim} Q${(a.x + b.x) / 2 + (mobile ? offset : 0)},${(a.y + b.y) / 2 + (mobile ? 0 : offset)} ${b.x - dx * trim},${b.y - dy * trim}`
            const reason = selected.factor_reasons.find(factor => factor.edge_id === item.id)
            const width = 1.5 + 3.5 * ((reason?.B ?? 0) / 3)
            const routeId = item.path_ids?.find(id => routes.some(route => route.path_id === id))
            const classes = ['ranked-edge', relationClass(item.predicate), evidenceClass(item.truth_class), highlightedEdgeIds.has(item.id) ? 'active' : '', selectedEdge === item.id ? 'inspected' : ''].filter(Boolean).join(' ')
            const edgeStyle = { '--edge-width': `${width.toFixed(2)}px` } as CSSProperties
            return <g key={item.id} className="ranked-edge-group" onMouseEnter={() => setHoveredRoute(routeId)} onMouseLeave={() => setHoveredRoute(undefined)} onFocus={() => setHoveredRoute(routeId)} onBlur={() => setHoveredRoute(undefined)}><path d={curve} className={classes} style={edgeStyle} markerEnd={`url(#route-arrow-${accountId})`} /><path d={curve} className="edge-hit" role="button" tabIndex={pending || error ? -1 : 0} aria-label={`Inspect ${relationshipPredicateLabel(item.predicate)}; ${relationshipEvidenceLabel(item.truth_class)}`} onClick={() => { if (!pending && !error) setSelectedEdge(item.id) }} onKeyDown={event => { if (!pending && !error && ['Enter', ' '].includes(event.key)) { event.preventDefault(); setSelectedEdge(item.id) } }}><title>{relationshipPredicateLabel(item.predicate)} · {relationshipEvidenceLabel(item.truth_class)}</title></path></g>
          })}
          {result?.graph.nodes.map(item => { const p = positions.get(item.id); if (!p) return null; const routeIndex = selected.node_ids.indexOf(item.id); const depth = visibleDepths.get(item.id); return <foreignObject key={item.id} data-node-id={item.id} x={p.x - 92} y={p.y - 60} width="184" height="120"><button disabled={pending || !!error} className={`${selected.node_ids.includes(item.id) ? 'active' : ''} node-${item.kind.toLocaleLowerCase().replaceAll('_', '-')}`} aria-pressed={selectedNode === item.id} aria-label={`${item.label}, ${label(item.kind)}${routeIndex >= 0 ? `, ${routeIndex === 0 ? 'route origin' : `hop ${routeIndex}`}` : ''}`} onClick={() => focusNode(item.id)}>{routeIndex >= 0 && <b className="ranked-hop-badge">{routeIndex === 0 ? 'O' : routeIndex}</b>}<span className="ranked-node-symbol" aria-hidden="true">{nodeSymbols[item.kind.toLocaleLowerCase()] ?? '•'}</span><span className="ranked-node-label">{item.label}</span><small>{label(item.kind)}{routeIndex < 0 && depth != null ? ` · depth ${depth}` : ''}</small></button></foreignObject> })}
        </svg></div></div><aside className="ranked-route-inspector" aria-label="Selected relationship explanation"><span className="eyebrow">Selected relationship route</span><h3>{selected.steps.at(-1)?.label}</h3><p><strong>Connection</strong>{selected.steps.map(step => step.label).join(' → ')}</p><p><strong>Why this route</strong>{selected.factor_reasons.map(factor => factor.reason).join(' ')}</p><p><strong>Weaker link</strong>{selected.factor_reasons.toSorted((a, b) => a.B - b.B || a.E - b.E)[0]?.reason ?? 'No substantive relationship factor is available.'}</p><p><strong>Supporting evidence</strong>{selected.evidence_ids.length} record{selected.evidence_ids.length === 1 ? '' : 's'} across {selected.hop_count} actual edges.</p>{selected.constraints.length > 0 && <p className="ranked-inspector-constraint"><strong>Execution constraint</strong>{selected.constraints.map(constraint => constraint.reason).join(' ')}</p>}<p><strong>Next action</strong>{selected.next_action}</p>{relatedIntelligence && <section><strong>Relevant intelligence</strong><p>{relatedIntelligence.assessment.headline}</p><p>{relatedIntelligence.assessment.why_it_may_matter}</p><p>{relatedIntelligence.assessment.recommended_action ?? 'Informational only; no action is established.'}</p></section>}<SupportingEvidence count={selected.evidence_ids.length} investigationKey={`relationship:${selected.path_id}:${result?.eligible_graph_revision}`}><p>The route score is {Number(selected.utility).toFixed(1)} under the provisional relationship rubric. It is not a probability, PWIN, qualification or capacity promise.</p><p>{selected.factor_reasons.map(factor => factor.reason).join(' ')}</p><p>{result?.intelligence_boundary}</p></SupportingEvidence></aside></div>
      {node && <div><p><strong>Focused entity:</strong> {node.label}. Selected route is unchanged.</p><button disabled={pending || !!error || (!expansions.includes(node.id) && expansions.length >= 8)} onClick={() => toggleExpansion(node.id)}>{expansions.includes(node.id) ? 'Collapse focused entity' : 'Expand focused entity'}</button></div>}
      {expansions.length > 0 && <details><summary>Open entity expansions · {expansions.length} of 8</summary>{expansions.map(id => <button key={id} disabled={pending || !!error} onClick={() => toggleExpansion(id)}>Collapse {result?.graph.nodes.find(item => item.id === id)?.label ?? id}</button>)}</details>}
      <details><summary>Visible relationships · keyboard and text equivalent</summary>{result?.graph.edges.map(item => <button key={item.id} disabled={pending || !!error} onClick={() => setSelectedEdge(item.id)}>{result.graph.nodes.find(value => value.id === item.source)?.label} → {relationshipPredicateLabel(item.predicate)} → {result.graph.nodes.find(value => value.id === item.target)?.label}<small>{relationshipEvidenceLabel(item.truth_class)} · {item.path_ids?.length ?? 0} returned routes share this relationship</small></button>)}</details>
      {edge && <aside aria-live="polite"><h4>{relationshipPredicateLabel(edge.predicate)}</h4><p>{relationshipDirectionLabel(false)}: {result?.graph.nodes.find(item => item.id === edge.source)?.label ?? 'Source entity'} → {result?.graph.nodes.find(item => item.id === edge.target)?.label ?? 'Target entity'}</p><p>{relationshipEvidenceLabel(edge.truth_class)} · observed {edge.observed_on ?? 'date unknown'}</p><label>Supporting record<select value={edge.evidence_ids.includes(evidenceId) ? evidenceId : ''} onChange={e => setEvidenceId(e.target.value)}><option value="">Choose a record to inspect</option>{edge.evidence_ids.map((id, index) => <option key={id} value={id}>Supporting record {index + 1}</option>)}</select></label>{edge.evidence_ids.includes(evidenceId) && <CommercialEvidence key={`${edge.account_id ?? accountId}:${evidenceId}`} accountId={edge.account_id ?? accountId} recordId={evidenceId} />}<details><summary>Authorized assertion detail</summary><p>{edge.lineage_groups.join(', ')}</p><small>Assertion {edge.id}</small></details></aside>}
      <details><summary>All returned routes · ordered text equivalent</summary>{routes.map((route, index) => <button key={route.path_id} data-route-id={route.path_id} aria-pressed={selected?.path_id === route.path_id} disabled={pending || !!error} onClick={() => selectRoute(route.path_id)}>Route {index + 1}: {route.steps.map(s => s.label).join(' → ')} · {route.hop_count} connections<small>{route.assertions?.map(a => `${relationshipPredicateLabel(a.predicate)} (${relationshipDirectionLabel(a.inverse)})`).join(' → ')}</small></button>)}{(result?.additional_route_count ?? 0) > 0 && <p>{result?.additional_route_count} additional evaluated routes are outside this response window.</p>}</details>
    </>}
  </section>
}
