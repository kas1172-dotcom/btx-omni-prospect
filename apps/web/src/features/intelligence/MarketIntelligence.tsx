import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Button, Disclosure, StatusBadge, StatusMessage } from '../../components/UI'
import { CanonicalRecord } from '../../components/CanonicalRecord'
import type { Account, OmniContext } from '../../types/api'
import type { MarketDetail, MarketOverview, MarketPoint, MarketTransformation } from '../../types/markets'
import type { WorkspaceLocation } from '../../app/navigation'
import { comparisonCompatibility, marketDecision, transformationLabel } from './marketPresentation'
import './markets.css'

const kinds: MarketTransformation[] = ['LEVEL', 'MOM_PERCENT', 'YOY_PERCENT']
function selectionFromLocation(location: WorkspaceLocation) {
  const page = Number(location.filters?.page ?? '0')
  const metric = String(location.filters?.metric ?? '')
  return { market: String(location.filters?.market ?? 'Semiconductor'), comparison: String(location.filters?.compare ?? ''), kind: kinds.includes(metric as MarketTransformation) ? metric as MarketTransformation : 'YOY_PERCENT' as MarketTransformation, average: location.filters?.average === '3', page: Number.isInteger(page) && page >= 0 && page <= 100 ? page : 0 }
}
const show = (point?: MarketPoint) => point?.value == null ? 'Unavailable' : Number(point.value).toLocaleString('en-US', { maximumFractionDigits: 2 })
const displayDate = (value?: string | null) => value ? new Date(value).toLocaleDateString() : 'Unavailable'

export function MarketIntelligence({ accounts, onAccount, onOmniContext, location, onLocationChange }: { accounts: Account[]; onAccount: (id: string) => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids'>) => void; location: WorkspaceLocation; onLocationChange: (next: WorkspaceLocation, mode?: 'push' | 'replace') => void }) {
  const selection = selectionFromLocation(location)
  const [overview, setOverview] = useState<MarketOverview>()
  const [detail, setDetail] = useState<MarketDetail>()
  const [errorKey, setErrorKey] = useState('')
  const [detailErrorKey, setDetailErrorKey] = useState('')
  const [settledKey, setSettledKey] = useState('')
  const [refresh, setRefresh] = useState(0)
  const requestKey = `${selection.kind}:${selection.average}:${refresh}`
  const pending = requestKey !== settledKey
  const error = errorKey === requestKey
  const choose = (next: typeof selection, mode: 'push' | 'replace' = 'push') => onLocationChange({ ...location, subview: 'markets', filters: { market: next.market, ...(next.comparison ? { compare: next.comparison } : {}), metric: next.kind, average: next.average ? '3' : '0', page: String(next.page) } }, mode)
  useEffect(() => {
    const controller = new AbortController()
    api.markets(selection.kind, selection.average, controller.signal).then(value => { if (!controller.signal.aborted) setOverview(value) }).catch(() => { if (!controller.signal.aborted) setErrorKey(requestKey) }).finally(() => { if (!controller.signal.aborted) setSettledKey(requestKey) })
    return () => controller.abort()
  }, [selection.kind, selection.average, requestKey])
  const effectiveKind = overview?.transformation ?? selection.kind
  const selected = overview?.series.find(series => series.metadata.markets.includes(selection.market))
  const comparison = selection.comparison ? overview?.series.find(series => series.metadata.markets.includes(selection.comparison)) : undefined
  const compatibility = selected && comparison ? comparisonCompatibility(selected.metadata, comparison.metadata) : undefined
  const detailKey = `${selected?.metadata.id}:${selected?.vintage_id}:${requestKey}`
  const detailError = detailErrorKey === detailKey
  useEffect(() => {
    onOmniContext({ active_filters: { market: selection.market, comparison_market: selection.comparison, market_metric: effectiveKind, market_average: overview?.moving_average_months ? '3' : '0', market_series_id: selected?.metadata.id ?? '', market_vintage_id: selected?.vintage_id ?? '' }, visible_record_ids: [selected?.metadata.id, comparison?.metadata.id].filter((value): value is string => Boolean(value)) })
  }, [onOmniContext, selection.market, selection.comparison, effectiveKind, selected, comparison, overview?.moving_average_months])
  useEffect(() => {
    if (!selected) return
    const controller = new AbortController()
    api.marketSeries(selected.metadata.id, effectiveKind, Boolean(overview?.moving_average_months), controller.signal).then(value => { if (!controller.signal.aborted) setDetail(value) }).catch(() => { if (!controller.signal.aborted) setDetailErrorKey(detailKey) })
    return () => controller.abort()
  }, [selected, effectiveKind, overview?.moving_average_months, detailKey])
  const currentDetail = detail?.metadata.id === selected?.metadata.id && detail?.vintage_id === selected?.vintage_id ? detail : undefined
  const exposed = accounts.filter(account => account.industries.includes(selection.market))
  const exposurePage = Math.min(selection.page, Math.max(0, Math.ceil(exposed.length / 8) - 1))
  const visibleExposure = exposed.slice(exposurePage * 8, (exposurePage + 1) * 8)
  const decision = selected ? marketDecision(selected, effectiveKind) : undefined
  const chartPoints = selected?.points.slice(-18) ?? []
  const comparisonPoints = compatibility?.compatible ? comparison?.points.slice(-18) ?? [] : []
  const numeric = chartPoints.flatMap(point => point.value == null ? [] : [Number(point.value)])
  const chartNumeric = [...numeric, ...comparisonPoints.flatMap(point => point.value == null ? [] : [Number(point.value)])]
  const minimum = Math.min(...chartNumeric), maximum = Math.max(...chartNumeric)
  const y = (value: number) => 160 - ((value - minimum) / (maximum - minimum || 1)) * 120
  const periods = [...new Set([...chartPoints, ...comparisonPoints].map(point => point.period))].sort().slice(-12)
  const stale = overview?.health.last_run?.status === 'FAILED'
  return <section className="surface market-intelligence" aria-labelledby="market-intelligence-title">
    <header className="page-title"><span className="eyebrow">Public economic context</span><h1 id="market-intelligence-title">Market Intelligence</h1><p>National manufacturing indicators for commercial investigation—not account orders or regional proof.</p></header>
    {pending && overview && <StatusMessage state="refreshing" title="Refreshing saved observations">Last-good observations remain visible with their saved labels.</StatusMessage>}
    {pending && !overview && <StatusMessage state="loading" title="Loading market observations">The selected series and URL state are retained.</StatusMessage>}
    {error && <StatusMessage state="error" title="Market observations unavailable" action={<Button onClick={() => setRefresh(value => value + 1)}>Retry this series</Button>}>{overview ? 'Last-good observations remain visible and are not labeled as freshly collected.' : 'No verified saved observation was returned, so no chart or table is shown.'}</StatusMessage>}
    {stale && overview && <StatusMessage state="stale" title="Saved observations may be stale">The latest source refresh failed. Previously verified values remain visible with their verification date.</StatusMessage>}
    {selected && decision && <section className="market-decision" aria-label="Market decision summary">
        <div><span className="eyebrow">What changed</span><h2>{selection.market} · {decision.direction}</h2><strong>{show(decision.latest)}{effectiveKind !== 'LEVEL' && decision.latest ? '%' : ''}</strong><p>{decision.latest?.period ?? 'Current period unavailable'} · {transformationLabel[effectiveKind]}{overview?.moving_average_months ? ' · three-month average' : ''}</p></div>
        <dl><div><dt>Measures</dt><dd>{decision.measure}</dd></div><div><dt>Unit</dt><dd>{decision.unit}</dd></div><div><dt>Cadence</dt><dd>{decision.cadence}</dd></div><div><dt>Geography</dt><dd>{decision.geography}</dd></div><div><dt>Verified</dt><dd>{displayDate(selected.last_verified_at)}</dd></div></dl>
        <article><h3>What it suggests</h3><p>{decision.commercialMeaning}</p></article><article><h3>What remains unknown</h3><p>{decision.limitation}</p></article><article><h3>What to investigate next</h3><p>{decision.nextAction}</p></article>
      </section>}
    <div className="market-controls">
      <label>BTX market<select value={selection.market} onChange={event => choose({ ...selection, market: event.target.value, comparison: event.target.value === selection.comparison ? '' : selection.comparison, page: 0 })}>{(overview?.coverage ?? [{ market: selection.market }]).map(row => <option key={row.market}>{row.market}</option>)}</select></label>
      <label>Metric / transformation<select value={selection.kind} onChange={event => choose({ ...selection, kind: event.target.value as MarketTransformation })}>{kinds.map(kind => <option key={kind} value={kind}>{transformationLabel[kind]}</option>)}</select></label>
      <label>Compare with<select value={selection.comparison} onChange={event => choose({ ...selection, comparison: event.target.value })}><option value="">No comparison</option>{overview?.coverage.filter(row => row.market !== selection.market).map(row => <option key={row.market}>{row.market}</option>)}</select></label>
      <label><input type="checkbox" checked={selection.average} onChange={event => choose({ ...selection, average: event.target.checked })} /> Three-month moving average</label>
      <Button disabled={pending} onClick={() => setRefresh(value => value + 1)}>Refresh saved observations</Button>
    </div>
    {selected && decision ? <>
      {selection.comparison && (!comparison || !compatibility?.compatible) && <StatusMessage state="not-applicable" title="Comparison unavailable">{comparison && compatibility ? compatibility.reason : 'The selected market has no collected series. No proxy comparison was invented.'}</StatusMessage>}
      {numeric.length > 0 && <figure className="market-trend"><svg viewBox="0 0 640 200" role="img" aria-label={`${selection.market} trend for the latest ${chartPoints.length} reporting periods. ${decision.direction}. Exact values are in the table.`}>
        <text x="8" y="22">{maximum.toFixed(2)}</text><text x="8" y="174">{minimum.toFixed(2)}</text>
        {[{ points: chartPoints, className: 'primary' }, ...(compatibility?.compatible && comparison ? [{ points: comparisonPoints, className: 'comparison' }] : [])].map(line => line.points.map((point, index) => point.value != null && <g key={`${line.className}:${point.period}`}>{index > 0 && line.points[index - 1].value != null && <line className={line.className} x1={65 + (index - 1) * 550 / Math.max(1, line.points.length - 1)} x2={65 + index * 550 / Math.max(1, line.points.length - 1)} y1={y(Number(line.points[index - 1].value))} y2={y(Number(point.value))} />}<circle className={line.className} cx={65 + index * 550 / Math.max(1, line.points.length - 1)} cy={y(Number(point.value))} r="3"><title>{point.period}: {show(point)}</title></circle></g>))}
        <text x="65" y="195">{chartPoints[0]?.period}</text><text x="555" y="195">{chartPoints.at(-1)?.period}</text>
      </svg><figcaption><span><i className="market-line-primary" />{selection.market}</span>{compatibility?.compatible && comparison && <span><i className="market-line-comparison" />{selection.comparison}</span>}<p>Latest {chartPoints.length} reporting periods. Gaps mean unavailable observations, never zero.</p></figcaption></figure>}
      {numeric.length > 0 && <div className="market-comparison-table"><table><caption>Aligned national series comparison · latest 12 periods</caption><thead><tr><th scope="col">Period</th><th scope="col">{selection.market}</th>{compatibility?.compatible && comparison && <th scope="col">{selection.comparison}</th>}</tr></thead><tbody>{periods.map(period => <tr key={period}><th scope="row">{period}</th><td>{show(selected.points.find(point => point.period === period))}</td>{compatibility?.compatible && comparison && <td>{show(comparison.points.find(point => point.period === period))}</td>}</tr>)}</tbody></table></div>}
      <Disclosure title="Full observation table"><div className="market-table-scroll" role="region" aria-label="Full saved market observations; scroll horizontally" tabIndex={0}><table><caption>{selected.metadata.title} · {selected.metadata.geography} · {selected.metadata.frequency}</caption><thead><tr><th scope="col">Period</th><th scope="col">Value</th></tr></thead><tbody>{selected.points.map(point => <tr key={point.period}><th scope="row">{point.period}</th><td>{show(point)}</td></tr>)}</tbody></table></div></Disclosure>
    </> : overview && <StatusMessage state="not-applicable" title="Series unavailable">No verified production series is available for this selected market. No proxy, regional or facility value has been invented.</StatusMessage>}
    <section aria-label="Canonical account exposure"><h2>Organizations with this market classification</h2><p>Canonical market membership, not predicted orders. Multi-market exposure is non-additive and does not allocate revenue.</p>{exposed.length ? <><p>{exposurePage * 8 + 1}–{Math.min((exposurePage + 1) * 8, exposed.length)} of {exposed.length} organizations</p><ul>{visibleExposure.map(account => <li key={account.id}><Button onClick={() => onAccount(account.id)}>{account.name ?? account.legal_name}</Button><span>{account.business_unit ? ` · ${account.business_unit}` : ''}</span></li>)}</ul><Button disabled={exposurePage === 0} onClick={() => choose({ ...selection, page: exposurePage - 1 })}>Previous organizations</Button><Button disabled={(exposurePage + 1) * 8 >= exposed.length} onClick={() => choose({ ...selection, page: exposurePage + 1 })}>Next organizations</Button></> : <StatusMessage state="empty">No canonical organization carries this market classification.</StatusMessage>}</section>
    <Disclosure title="Source, transformation and vintage evidence">{detailError && <StatusMessage state="error">Source evidence could not be loaded. Refresh this series to retry without changing the selected market.</StatusMessage>}{currentDetail ? <><div className="market-source-summary"><StatusBadge value="Public intelligence" tone="info" /><a href={selected?.metadata.source_url} target="_blank" rel="noreferrer">Federal Reserve Board source</a></div><CanonicalRecord value={{ series_identifier: currentDetail.metadata.id, native_series_code: currentDetail.metadata.native_code, metadata: currentDetail.metadata, vintage_id: currentDetail.vintage_id, retrieved_at: currentDetail.retrieved_at, last_verified_at: currentDetail.last_verified_at, release_date: currentDetail.release_date ?? 'Publication date unavailable; retrieval date is not substituted', retrieval_kind: currentDetail.retrieval_kind, transformation: currentDetail.transformation, moving_average_months: currentDetail.moving_average_months, source_sha256: currentDetail.source_sha256, source_title: currentDetail.source_title, vintages: currentDetail.vintages, source_health: currentDetail.source_health }} /></> : <p>No matching source evidence is loaded for the selected series.</p>}<CanonicalRecord value={overview?.coverage} /></Disclosure>
  </section>
}
