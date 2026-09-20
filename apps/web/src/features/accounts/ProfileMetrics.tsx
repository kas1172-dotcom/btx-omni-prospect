import type { CommercialDecision } from '../../types/decisions'
import type { MonthlyCommercial } from '../../types/accountProfile'

export function HealthValue({ decision, band }: { decision?: CommercialDecision | null; band?: string | null }) {
  if (!decision || decision.status === 'INELIGIBLE') return <span>—</span>
  const coverage = Number(decision.data_coverage.ratio) * 100
  const value = coverage < 100 && decision.score_range ? `${decision.score_range.low}–${decision.score_range.high}` : decision.score ?? 'Unknown'
  return <span className="profile-metric-score"><strong>{value}</strong><span className="profile-band" title={band ?? 'Health band not configured by scoring service'}>● <small>{band ?? 'Band unavailable'}</small></span><small>Data Coverage {coverage.toFixed(0)}%</small></span>
}

export function BookingsSparkline({ months, delta }: { months: Array<{ period: string; bookings_minor: number }>; delta?: string | null }) {
  if (!months.length) return <span>—</span>
  const max = Math.max(...months.map(row => row.bookings_minor), 1)
  const points = months.map((row, i) => `${5 + i * 110 / Math.max(months.length - 1, 1)},${31 - row.bookings_minor / max * 27}`).join(' ')
  return <details className="profile-sparkline"><summary><svg viewBox="0 0 120 36" role="img" aria-label="Recorded monthly bookings; expand for values"><polyline fill="none" stroke="currentColor" strokeWidth="2" points={points} /></svg><span>{delta == null ? 'Delta unknown' : `${Number(delta) >= 0 ? '+' : ''}${(Number(delta) * 100).toFixed(1)}%`}</span></summary><small>Latest 3 months vs prior 3 months</small><table><thead><tr><th>Month</th><th>Bookings (minor units)</th></tr></thead><tbody>{months.map(row => <tr key={row.period}><td>{row.period}</td><td>{row.bookings_minor.toLocaleString()}</td></tr>)}</tbody></table></details>
}

export function RevenueChart({ months, currency }: { months: MonthlyCommercial[]; currency: string }) {
  if (!months.length) return <p>No monthly commercial history is linked.</p>
  const max = Math.max(...months.flatMap(row => [row.revenue_minor, row.bookings_minor]), 1)
  const points = months.map((row, i) => `${30 + i * 540 / Math.max(months.length - 1, 1)},${160 - row.bookings_minor / max * 140}`).join(' ')
  const money = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value / 100)
  return <><p>Revenue bars · Bookings dashed line · {currency} · SAMPLE</p><svg className="profile-revenue-chart" viewBox="0 0 600 190" role="img" aria-label="Monthly revenue bars and bookings dashed line. Exact values in the table below.">{months.map((row, i) => <g key={row.period}><rect x={18 + i * 540 / Math.max(months.length - 1, 1)} y={160 - row.revenue_minor / max * 140} width="22" height={row.revenue_minor / max * 140} fill="#37667d" /><text x={30 + i * 540 / Math.max(months.length - 1, 1)} y="180" textAnchor="middle" fontSize="9">{row.period.slice(5)}</text></g>)}<polyline fill="none" stroke="#976b26" strokeWidth="3" strokeDasharray="5 3" points={points} /></svg><details><summary>Monthly values and source records</summary><table className="profile-table"><thead><tr><th>Month</th><th>Revenue</th><th>Bookings</th><th>Source</th></tr></thead><tbody>{months.map(row => <tr key={row.snapshot_id}><td>{row.period}</td><td>{money(row.revenue_minor)}</td><td>{money(row.bookings_minor)}</td><td>{row.snapshot_id} · SAMPLE</td></tr>)}</tbody></table></details></>
}
