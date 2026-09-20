import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
import { createRequire } from 'node:module'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

async function load(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
}
const m = await load('../src/features/opportunities/opportunityModel.ts')
const { opportunityFixture: rows } = await load('../src/features/opportunities/opportunityFixture.ts')
const nav = await load('../src/app/navigation.ts')
const view = m.readView({ surface: 'opportunities' })
const ids = rows => rows.map(r => r.opportunity_id)

test('priority ranks complete scores before incomplete ranges even with higher range tops', () => {
  const sorted = m.sortRows(rows)
  assert.deepEqual(sorted.slice(0, 6).map(r => r.opportunity_priority.score), [82, 79, 76, 68, 61, 41])
  assert.deepEqual(sorted.slice(6).map(r => r.opportunity_priority.score_range.high), [80, 78, 75, 72, 70, 60])
  assert.equal(m.sortRows(rows, 'priority-asc')[0].opportunity_priority.score, 41)
})
test('all sort ties end in opportunity ID and never mutate the input', () => {
  const twins = [{ ...rows[0], opportunity_id: 'z' }, { ...rows[0], opportunity_id: 'a' }]
  for (const column of ['company', 'market', 'stage', 'value', 'priority', 'status']) {
    for (const direction of ['asc', 'desc']) assert.deepEqual(ids(m.sortRows(twins, `${column}-${direction}`)), ['a', 'z'])
  }
  assert.equal(twins[0].opportunity_id, 'z')
})
test('company sorting is locale-aware and case-insensitive', () => {
  const mixed = ['zeta', 'acme', 'ACME', 'Éclair'].map((account_name, index) => ({ ...rows[0], account_name, opportunity_id: String(index) }))
  assert.deepEqual(ids(m.sortRows(mixed, 'company-asc')), ['1', '2', '3', '0'])
})
test('status order and chip semantics follow qualification and durability', () => {
  assert.deepEqual([...new Set(m.sortRows(rows, 'status-asc').map(m.statusOf).map(s => s.label))], ['Qualified and durable', 'Qualified', 'Needs research', 'Not qualified'])
  assert.equal(m.statusOf({ ...rows[0], qualification_status: 'NO', durability_status: 'YES' }).label, 'Not qualified')
})
test('incomplete scores display backend range, never a point estimate', () => {
  assert.equal(m.priorityOf(rows[5]).text, '45 to 75')
  assert.equal(m.priorityOf({ ...rows[5], opportunity_priority: { ...rows[5].opportunity_priority, score: 45 } }).score, null)
  assert.equal(m.priorityOf({ ...rows[5], opportunity_priority: { ...rows[5].opportunity_priority, score_range: undefined } }).text, 'Unavailable')
  assert.equal(m.priorityOf(rows[0]).band, 'High priority')
  assert.equal(m.priorityOf(rows[2]).band, 'Worth developing')
  assert.equal(m.priorityOf(rows[4]).band, 'Lower priority')
})
test('filters intersect lane, multiple markets, BU, stage, text and account', () => {
  const filtered = m.filterRows(rows, { ...view, markets: ['Defense', 'Commercial Aerospace'], bu: 'Chandler', stage: 'QUALIFICATION', query: 'HOUSINGS' })
  assert.deepEqual(ids(filtered), ['dev-raytheon'])
  assert.deepEqual(ids(m.filterRows(rows, { ...view, account: 'dev-account-honeywell' })), ['dev-honeywell'])
  assert.equal(m.filterRows(rows, { ...view, lane: 'PROSPECT' }).length, 5)
  assert.equal(m.filterRows(rows, { ...view, lane: 'PROSPECT', markets: ['Unassigned'] })[0].account_name, 'Boston Dynamics')
})
test('saved views use the backend booleans, not frontend scoring guesses', () => {
  assert.deepEqual(ids(m.filterRows(rows, { ...view, saved: 'qualified-durable' })), ['dev-honeywell', 'dev-northrop'])
  assert.deepEqual(ids(m.filterRows(rows, { ...view, saved: 'best-bets' })), ['dev-honeywell'])
  assert.equal(m.filterRows([{ ...rows[0], gates: undefined }], { ...view, saved: 'qualified-durable' }).length, 0)
  assert.equal(m.filterRows([{ ...rows[4], gates: { qualified_and_durable: true, durable_best_bet: true } }], { ...view, saved: 'best-bets' }).length, 1)
})
test('groups are alphabetical, Unassigned last, preserving active row sort and subtotal', () => {
  const groups = m.groupRows(m.sortRows(rows), 'market')
  assert.equal(groups[0].name, 'Commercial Aerospace')
  assert.equal(groups.at(-1).name, 'Unassigned')
  assert.equal(groups.find(g => g.name === 'Space').subtotal, '$660K')
  assert.deepEqual(ids(groups.find(g => g.name === 'Defense').rows), ['dev-northrop', 'dev-raytheon', 'dev-lockheed', 'dev-kratos'])
  for (const group of ['none', 'company', 'bu', 'stage']) assert.equal(m.groupRows(rows, group).flatMap(g => g.rows).length, rows.length)
})
test('unsized values stay unsized and different currencies are not summed together', () => {
  assert.equal(m.money(null), 'Not sized')
  assert.equal(m.subtotal([rows[6]]), 'Not sized')
  assert.equal(m.subtotal([{ ...rows[0], value_minor: 10000 }, { ...rows[0], value_minor: 20000, currency: 'EUR' }]), '€200 + $100')
  assert.equal(m.sortRows(rows, 'value-desc').at(-1).value_minor, null)
})
test('market counts apply other filters, preserve zero-count options and ignore their own selection', () => {
  const options = m.marketOptions(rows, { ...view, markets: ['Defense'] })
  assert.equal(options.find(o => o.label === 'Defense').count, 3)
  assert.equal(options.find(o => o.label === 'Commercial Aerospace').count, 2)
  assert.equal(options.find(o => o.label === 'Space').count, 0)
})
test('URL round-trip restores every view field, selection, fixture and return context', () => {
  const original = { ...view, lane: 'PROSPECT', query: 'valve & mount', markets: ['Defense', 'Space'], bu: 'ERA', stage: 'DISCOVERY', saved: 'best-bets', group: 'market', sort: 'value-desc', collapsed: ['Defense', 'Space'] }
  const location = m.viewLocation({ surface: 'opportunities', filters: { opportunity_fixture: 'demo' }, returnTo: { surface: 'accounts', accountId: 'honeywell' } }, original, 'dev-spacex')
  const decoded = nav.workspaceLocation(nav.workspaceHash(location))
  assert.deepEqual(m.readView(decoded), original)
  assert.equal(decoded.recordId, 'dev-spacex')
  assert.equal(decoded.filters.opportunity_fixture, 'demo')
  assert.equal(decoded.returnTo.accountId, 'honeywell')
})
test('header cycles ascending descending default; clear filters retains lane and sorting', () => {
  assert.equal(m.nextSort('default', 'company'), 'company-asc')
  assert.equal(m.nextSort('company-asc', 'company'), 'company-desc')
  assert.equal(m.nextSort('company-desc', 'company'), 'default')
  const clear = m.clearFilters({ ...view, query: 'x', lane: 'PROSPECT', group: 'bu', sort: 'value-desc', markets: ['Defense'], saved: 'best-bets' })
  assert.equal(m.hasFilters(clear), false)
  assert.equal(clear.lane, 'PROSPECT')
  assert.equal(clear.group, 'bu')
  assert.equal(clear.sort, 'value-desc')
})

test('priority cell renders the exact backend range and dashed segment, never a point', async () => {
  const source = await readFile(new URL('../src/features/opportunities/PriorityCell.tsx', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } })
  const exports = {}
  const require = createRequire(import.meta.url)
  new Function('require', 'exports', outputText)(name => name === './opportunityModel' ? m : require(name), exports)
  const html = renderToStaticMarkup(createElement(exports.PriorityCell, { row: rows[5], showBand: true }))
  assert.match(html, />45 to 75</)
  assert.match(html, /class="opp-range" style="left:45%;width:30%"/)
  assert.match(html, /Incomplete/)
  assert.doesNotMatch(html, />45</)
  const complete = renderToStaticMarkup(createElement(exports.PriorityCell, { row: rows[0] }))
  assert.match(complete, />82</)
  assert.match(complete, /width:82%/)
})

test('fixture covers requested missing-factor and gate states without category inference', () => {
  assert.equal(rows[5].opportunity_priority.factors.filter(f => f.points === null).length, 1)
  assert.equal(rows[6].opportunity_priority.factors.filter(f => f.points === null).length, 2)
  assert.equal(new Set(rows.map(r => r.qualification_status)).size, 3)
  assert.equal(new Set(rows.map(r => r.durability_status)).size, 3)
  assert.ok(new Set(rows.map(r => r.market)).size >= 4)
})
