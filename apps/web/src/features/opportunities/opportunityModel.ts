import type { WorkspaceLocation } from '../../app/navigation'
import type { Opportunity } from '../../types/opportunities'

export type SortColumn = 'company' | 'market' | 'stage' | 'value' | 'priority' | 'status'
export type GroupBy = 'none' | 'company' | 'market' | 'bu' | 'stage'
export type SavedView = 'all' | 'qualified-durable' | 'best-bets'
export type OpportunityView = {
  lane: 'CUSTOMER_EXPANSION' | 'PROSPECT'; query: string; account: string
  markets: string[]; bu: string; stage: string; saved: SavedView; group: GroupBy
  sort: string; collapsed: string[]
}
const collator = new Intl.Collator('en', { sensitivity: 'base', numeric: true })
const strings = (value?: string | string[]) => value == null ? [] : Array.isArray(value) ? value : [value]
const first = (value?: string | string[]) => strings(value)[0] ?? ''
export const UNASSIGNED = 'Unassigned'
export const category = (value?: string | null) => value?.trim() || UNASSIGNED
export const words = (value: string) => value.replaceAll('_', ' ').toLowerCase().replace(/^./, letter => letter.toUpperCase())
export const stageLabel = (stage: string) => ({ PROPOSAL: 'Proposal', PROPOSAL_APPROVED: 'Proposal approved', QUALIFY: 'Qualification', QUALIFICATION: 'Qualification', QUALIFIED: 'Qualified', QUOTED: 'Quoted', NEGOTIATION: 'Negotiation', DISCOVERY: 'Discovery', RESEARCH: 'Research' }[stage] ?? words(stage))
export const sortOptions = [
  ['default', 'Priority, high to low'], ['company-asc', 'Company, A to Z'], ['value-desc', 'Value, high to low'],
  ['stage-asc', 'Stage'], ['market-asc', 'Market, A to Z'], ['status-asc', 'Status'],
] as const
export const groupOptions: Array<[GroupBy, string]> = [['none', 'None'], ['company', 'Company'], ['market', 'Market'], ['bu', 'BU'], ['stage', 'Stage']]
export function readView(location: WorkspaceLocation): OpportunityView {
  const f = location.filters ?? {}
  const saved = first(f.opportunity_view), group = first(f.opportunity_group)
  return {
    lane: f.lane === 'PROSPECT' ? 'PROSPECT' : 'CUSTOMER_EXPANSION', query: first(f.query), account: first(f.account),
    markets: strings(f.market), bu: first(f.business_unit), stage: first(f.opportunity_stage),
    saved: saved === 'qualified-durable' || saved === 'best-bets' ? saved : 'all',
    group: groupOptions.some(([key]) => key === group) ? group as GroupBy : 'none',
    sort: /^(company|market|stage|value|priority|status)-(asc|desc)$/.test(location.sort ?? '') ? location.sort! : 'default',
    collapsed: strings(f.opportunity_collapsed),
  }
}
export function viewLocation(location: WorkspaceLocation, view: OpportunityView, recordId?: string): WorkspaceLocation {
  const filters = { ...location.filters }
  for (const key of ['lane', 'query', 'account', 'market', 'business_unit', 'opportunity_stage', 'opportunity_view', 'opportunity_group', 'opportunity_collapsed']) delete filters[key]
  Object.assign(filters, { lane: view.lane, opportunity_view: view.saved, opportunity_group: view.group })
  if (view.query) filters.query = view.query
  if (view.account) filters.account = view.account
  if (view.markets.length) filters.market = view.markets
  if (view.bu) filters.business_unit = view.bu
  if (view.stage) filters.opportunity_stage = view.stage
  if (view.collapsed.length) filters.opportunity_collapsed = view.collapsed
  return { ...location, filters, sort: view.sort, recordId }
}
export const clearFilters = (view: OpportunityView): OpportunityView => ({ ...view, query: '', account: '', markets: [], bu: '', stage: '', saved: 'all' })
export const hasFilters = (view: OpportunityView) => Boolean(view.query || view.account || view.markets.length || view.bu || view.stage || view.saved !== 'all')
export function statusOf(row: Opportunity): { label: string; tone: string; order: number } {
  if (row.qualification_status === 'NO') return { label: 'Not qualified', tone: 'no', order: 3 }
  if (row.qualification_status === 'YES' && row.durability_status === 'YES') return { label: 'Qualified and durable', tone: 'durable', order: 0 }
  if (row.qualification_status === 'YES') return { label: 'Qualified', tone: 'qualified', order: 1 }
  return { label: 'Needs research', tone: 'unknown', order: 2 }
}
const number = (value: unknown): number | null => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value)
export function priorityOf(row: Opportunity) {
  const decision = row.opportunity_priority
  const score = number(decision.score)
  const complete = score != null && number(decision.data_coverage.ratio) === 1 && !['BLOCKED', 'INELIGIBLE'].includes(decision.status)
  const low = number(decision.score_range?.low), high = number(decision.score_range?.high)
  const range = !complete && low != null && high != null && low >= 0 && high <= 100 && low <= high
  const format = (value: number) => value.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return {
    complete, score: complete ? score : null, low: range ? low : null, high: range ? high : null,
    text: complete ? format(score) : range ? `${format(low)} to ${format(high)}` : 'Unavailable',
    band: !complete ? 'Incomplete' : score >= 75 ? 'High priority' : score >= 50 ? 'Worth developing' : 'Lower priority',
    tone: !complete ? 'incomplete' : score >= 75 ? 'high' : score >= 50 ? 'mid' : 'low',
  }
}
export function compareCategory(a: string, b: string) {
  return a === b ? 0 : a === UNASSIGNED ? 1 : b === UNASSIGNED ? -1 : collator.compare(a, b)
}
export function nextSort(current: string, column: SortColumn) {
  return current === `${column}-asc` ? `${column}-desc` : current === `${column}-desc` ? 'default' : `${column}-asc`
}
export function sortRows(rows: Opportunity[], sort = 'default') {
  const [key, order] = (sort === 'default' ? 'priority-desc' : sort).split('-')
  const direction = order === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    let compared: number
    if (key === 'priority') {
      const x = priorityOf(a), y = priorityOf(b)
      if (x.complete !== y.complete) return x.complete ? -1 : 1
      const av = x.complete ? x.score : x.high, bv = y.complete ? y.score : y.high
      if (av == null || bv == null) compared = av === bv ? 0 : av == null ? 1 : -1
      else compared = (av - bv) * direction
    } else if (key === 'value') {
      // Different currencies are ordered by currency, never implicitly converted.
      if (a.value_minor == null || b.value_minor == null) compared = a.value_minor === b.value_minor ? 0 : a.value_minor == null ? 1 : -1
      else compared = collator.compare(a.currency, b.currency) || (a.value_minor - b.value_minor) * direction
    } else if (key === 'status') compared = (statusOf(a).order - statusOf(b).order) * direction
    else if (key === 'market') {
      const x = category(a.market), y = category(b.market)
      compared = x === UNASSIGNED || y === UNASSIGNED ? compareCategory(x, y) : collator.compare(x, y) * direction
    } else compared = collator.compare(key === 'company' ? a.account_name : stageLabel(a.stage), key === 'company' ? b.account_name : stageLabel(b.stage)) * direction
    return compared || a.opportunity_id.localeCompare(b.opportunity_id, 'en')
  })
}
export function filterRows(rows: Opportunity[], view: OpportunityView, ignoreMarket = false) {
  const query = view.query.trim().toLocaleLowerCase('en')
  return rows.filter(row => row.lane === view.lane
    && (!view.account || row.account_id === view.account)
    && (!query || `${row.account_name} ${row.title}`.toLocaleLowerCase('en').includes(query))
    && (ignoreMarket || !view.markets.length || view.markets.includes(category(row.market)))
    && (!view.bu || category(row.bu) === view.bu) && (!view.stage || row.stage === view.stage)
    && (view.saved === 'all' || (view.saved === 'qualified-durable' ? row.gates?.qualified_and_durable === true : row.gates?.durable_best_bet === true)))
}
export function money(value: number | null, currency = 'USD') {
  return value == null ? 'Not sized' : new Intl.NumberFormat('en-US', { style: 'currency', currency, notation: 'compact', minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(value / 100)
}
export function subtotal(rows: Opportunity[]) {
  const currencies = new Map<string, number>()
  for (const row of rows) if (row.value_minor != null) currencies.set(row.currency, (currencies.get(row.currency) ?? 0) + row.value_minor)
  return [...currencies].sort(([a], [b]) => a.localeCompare(b)).map(([currency, value]) => money(value, currency)).join(' + ') || 'Not sized'
}
export function groupRows(rows: Opportunity[], group: GroupBy) {
  if (group === 'none') return [{ name: '', rows, subtotal: subtotal(rows) }]
  const groups = new Map<string, Opportunity[]>()
  for (const row of rows) {
    const name = group === 'company' ? row.account_name : group === 'stage' ? stageLabel(row.stage) : category(row[group])
    groups.set(name, [...(groups.get(name) ?? []), row])
  }
  return [...groups].sort(([a], [b]) => compareCategory(a, b)).map(([name, entries]) => ({ name, rows: entries, subtotal: subtotal(entries) }))
}
export function marketOptions(rows: Opportunity[], view: OpportunityView) {
  const eligible = filterRows(rows, view, true)
  return [...new Set([...rows.map(row => category(row.market)), ...view.markets])].sort(compareCategory)
    .map(label => ({ label, count: eligible.filter(row => category(row.market) === label).length }))
}
