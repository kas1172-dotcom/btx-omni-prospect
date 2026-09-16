import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import { Button, Disclosure } from '../../components/UI'
import { CanonicalRecord } from '../../components/CanonicalRecord'
import type { Account, OmniContext } from '../../types/api'
import type { MarketDetail, MarketOverview, MarketPoint, MarketTransformation } from '../../types/markets'
import './markets.css'
import type { WorkspaceLocation } from '../../app/navigation'

const kinds: MarketTransformation[] = ['LEVEL', 'MOM_PERCENT', 'YOY_PERCENT']
const kindLabel = { LEVEL: 'Production index · 2017=100', MOM_PERCENT: 'Month-over-month change · %', YOY_PERCENT: 'Year-over-year change · %' }
function selectionFromLocation(location: WorkspaceLocation) { const page = Number(location.filters?.page ?? '0'); const metric = String(location.filters?.metric ?? ''); return { market: String(location.filters?.market ?? 'Semiconductor'), kind: kinds.includes(metric as MarketTransformation) ? metric as MarketTransformation : 'YOY_PERCENT' as MarketTransformation, average: location.filters?.average === '3', page: Number.isInteger(page) && page >= 0 && page <= 100 ? page : 0 } }
const show = (point?: MarketPoint) => point?.value == null ? '—' : Number(point.value).toLocaleString('en-US', { maximumFractionDigits: 2 })

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
  const choose = (next: typeof selection) => {
    onLocationChange({ ...location, subview: 'markets', filters: { market: next.market, metric: next.kind, average: next.average ? '3' : '0', page: String(next.page) } }, 'replace')
  }
  useEffect(() => {
    const controller = new AbortController()
    api.markets(selection.kind, selection.average, controller.signal).then(value => { if (!controller.signal.aborted) setOverview(value) })
      .catch(() => { if (!controller.signal.aborted) setErrorKey(requestKey) })
      .finally(() => { if (!controller.signal.aborted) setSettledKey(requestKey) })
    return () => controller.abort()
  }, [selection.kind, selection.average, requestKey])
  // Previous content remains visible only with its own metric labels; do not
  // relabel stale observations as a newly selected transformation.
  const effectiveKind = overview?.transformation ?? selection.kind
  const selected = overview?.series.find(series => series.metadata.markets.includes(selection.market))
  const detailKey = `${selected?.metadata.id}:${selected?.vintage_id}:${requestKey}`
  const detailError = detailErrorKey === detailKey
  useEffect(() => {
    onOmniContext({ active_filters: { market: selection.market, market_metric: effectiveKind, market_average: overview?.moving_average_months ? '3' : '0', market_series_id: selected?.metadata.id ?? '', market_vintage_id: selected?.vintage_id ?? '' }, visible_record_ids: selected ? [selected.metadata.id] : [] })
  }, [onOmniContext, selection.market, effectiveKind, selected, overview?.moving_average_months])
  useEffect(() => {
    if (!selected) return
    const controller = new AbortController()
    api.marketSeries(selected.metadata.id, effectiveKind, Boolean(overview?.moving_average_months), controller.signal)
      .then(value => { if (!controller.signal.aborted) setDetail(value) })
      .catch(() => { if (!controller.signal.aborted) setDetailErrorKey(detailKey) })
    return () => controller.abort()
  }, [selected, effectiveKind, overview?.moving_average_months, detailKey])
  const currentDetail = detail?.metadata.id === selected?.metadata.id && detail?.vintage_id === selected?.vintage_id ? detail : undefined
  const periods = useMemo(() => [...new Set(overview?.series.flatMap(series => series.points.map(point => point.period)) ?? [])].sort(), [overview])
  const exposed = accounts.filter(account => account.industries.includes(selection.market))
  const exposurePage = Math.min(selection.page, Math.max(0, Math.ceil(exposed.length / 8) - 1))
  const visibleExposure = exposed.slice(exposurePage * 8, (exposurePage + 1) * 8)
  const points = selected?.points ?? []
  const numeric = points.flatMap(point => point.value == null ? [] : [Number(point.value)])
  const minimum = Math.min(...numeric), maximum = Math.max(...numeric)
  const y = (value: number) => 160 - ((value - minimum) / (maximum - minimum || 1)) * 120
  const latest = points.at(-1)
  return <section className="surface market-intelligence" aria-labelledby="market-intelligence-title">
    <header className="page-title"><span className="eyebrow">Public economic context</span><h1 id="market-intelligence-title">Market Intelligence</h1><p>Published manufacturing trends and exposed accounts.</p></header>
    {selected && <div className="market-scorecard"><span>{selection.market} · {kindLabel[effectiveKind]}{overview?.moving_average_months ? ' · 3-month average' : ''}</span><strong>{show(latest)}{effectiveKind !== 'LEVEL' && latest?.value != null ? '%' : ''}</strong><span>{latest?.period ?? 'Period unavailable'} · National United States · Seasonally adjusted</span><a href={selected.metadata.source_url} target="_blank" rel="noreferrer">Federal Reserve Board source</a></div>}
    <div className="market-controls">
      <label>BTX market<select value={selection.market} onChange={event => choose({ ...selection, market: event.target.value, page: 0 })}>{(overview?.coverage ?? [{ market: selection.market }]).map(row => <option key={row.market}>{row.market}</option>)}</select></label>
      <label>Metric / transformation<select value={selection.kind} onChange={event => choose({ ...selection, kind: event.target.value as MarketTransformation })}>{kinds.map(kind => <option key={kind} value={kind}>{kindLabel[kind]}</option>)}</select></label>
      <label><input type="checkbox" checked={selection.average} onChange={event => choose({ ...selection, average: event.target.checked })} /> Three-month moving average</label>
      <Button disabled={pending} onClick={() => setRefresh(value => value + 1)}>Refresh saved observations</Button>
    </div>
    <p role="status">{pending ? 'Loading selected market observations… Existing values retain their prior labels.' : overview ? 'Saved public observations loaded.' : 'No market observations loaded.'}</p>
    {error && <p role="alert">Market data could not be loaded. Your selection is retained. <Button onClick={() => setRefresh(value => value + 1)}>Retry saved observations</Button></p>}
    {overview?.health.last_run?.status === 'FAILED' && <p role="alert">The latest source refresh failed. Previously verified observations remain available; they have not been reverified.</p>}
    {!overview && error ? <p>No chart or comparison table is shown because no verified saved observation was returned.</p> : <><h2>{selection.market}</h2>
    {selected ? <>
      <p>{selected.metadata.title} · {selected.metadata.taxonomy} {selected.metadata.naics} · National United States · Seasonally adjusted</p>
      <p>{selected.metadata.limitation}</p>
      {numeric.length > 0 && <figure className="market-trend"><svg viewBox="0 0 640 200" role="img" aria-label={`${selection.market}: ${kindLabel[effectiveKind]}. Exact values are in the table below.`}>
        <text x="8" y="22">{maximum.toFixed(2)}</text><text x="8" y="174">{minimum.toFixed(2)}</text>
        {points.map((point, index) => point.value != null && <g key={point.period}>{index > 0 && points[index - 1].value != null && <line x1={65 + (index - 1) * 550 / Math.max(1, points.length - 1)} x2={65 + index * 550 / Math.max(1, points.length - 1)} y1={y(Number(points[index - 1].value))} y2={y(Number(point.value))} />}<circle cx={65 + index * 550 / Math.max(1, points.length - 1)} cy={y(Number(point.value))} r="2"><title>{point.period}: {show(point)}</title></circle></g>)}
        <text x="65" y="195">{points[0]?.period}</text><text x="555" y="195">{latest?.period}</text>
      </svg><figcaption>36 reporting months; gaps are missing observations, not zero. {kindLabel[effectiveKind]}{overview?.moving_average_months ? '; average of three calendar-month transformed values' : ''}.</figcaption></figure>}
    </> : <p>No verified production series is available for this selected market. No proxy values have been invented.</p>}
    <h2>Market-by-month comparison</h2><p>{kindLabel[effectiveKind]}{overview?.moving_average_months ? ' · 3-month average' : ''}. Dark cells: {effectiveKind === 'LEVEL' ? 'at or above the 2017 index base of 100' : 'non-negative change'}; light cells: below that reference. These are comparison bands, not investment quality. Aerospace, Defense and Space repeat the same broad series; do not add them together. A dash means unavailable.</p>
    <div className="market-table-scroll" role="region" aria-label="Market by month values; scroll horizontally" tabIndex={0}><table><caption>National industrial production · compatible monthly series</caption><thead><tr><th scope="col">Market</th>{periods.map(period => <th scope="col" key={period}>{period}</th>)}</tr></thead><tbody>{overview?.coverage.map(row => {
      const series = overview.series.find(item => row.series_ids.includes(item.metadata.id))
      return <tr key={row.market}><th scope="row"><button onClick={() => choose({ ...selection, market: row.market, page: 0 })} aria-pressed={selection.market === row.market}>{row.market}</button></th>{periods.map(period => { const point = series?.points.find(item => item.period === period); const value = point?.value == null ? null : Number(point.value); const intensity = value == null ? '' : effectiveKind === 'LEVEL' ? value >= 100 ? 'high' : 'low' : value >= 0 ? 'high' : 'low'; return <td key={period} className={intensity}>{show(point)}</td> })}</tr>
    })}</tbody></table></div>
    <Disclosure title="Regional availability"><p>Regional industrial production for these industry series is unavailable. National values are not assigned to states. Regional manufacturing employment is a separate metric and is not yet connected here.</p></Disclosure></>}
    <section aria-label="Canonical account exposure"><h2>Exposed accounts</h2><p>Canonical market membership, not predicted orders. Multi-market exposure is non-additive; no revenue allocation is implied.</p>{exposed.length ? <><p>{exposurePage * 8 + 1}–{Math.min((exposurePage + 1) * 8, exposed.length)} of {exposed.length} accounts</p><ul>{visibleExposure.map(account => <li key={account.id}><Button onClick={() => onAccount(account.id)}>{account.name ?? account.legal_name}</Button><span>{account.business_unit ? ` · ${account.business_unit}` : ''}</span></li>)}</ul><Button disabled={exposurePage === 0} onClick={() => choose({ ...selection, page: exposurePage - 1 })}>Previous accounts</Button><Button disabled={(exposurePage + 1) * 8 >= exposed.length} onClick={() => choose({ ...selection, page: exposurePage + 1 })}>Next accounts</Button></> : <p>No canonical accounts match this market in your current workspace.</p>}</section>
    <Disclosure title="Source, vintage and coverage audit">{detailError && <p role="alert">Source audit could not be loaded. Retry without changing your market.</p>}{currentDetail ? <CanonicalRecord value={{ metadata: currentDetail.metadata, vintage_id: currentDetail.vintage_id, retrieved_at: currentDetail.retrieved_at, last_verified_at: currentDetail.last_verified_at, retrieval_kind: currentDetail.retrieval_kind ?? 'Not recorded by this earlier vintage; inspect its refresh receipt', release_date: currentDetail.release_date ?? 'Not extracted; retrieval date is not publication date', source_sha256: currentDetail.source_sha256, source_title: currentDetail.source_title, vintages: currentDetail.vintages, source_health: currentDetail.source_health }} /> : <p>No matching source audit loaded for the selected series.</p>}<CanonicalRecord value={overview?.coverage} /></Disclosure>
  </section>
}
