import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/features/map/mapModel.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { markersForZoom, validCoordinates, haversineMiles, filterMapRecords } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const marker = (id, latitude, longitude, kind = 'customer') => ({ id, latitude, longitude, kind, label: id, accessibleLabel: id })
const ids = result => result.flatMap(item => item.memberIds ?? [item.id]).sort()

test('NAICS and commercial BU filters intersect without inventing missing assignments or geography', () => {
  const filters = { coverage: 'ALL', top100: false, industries: [], relationships: [], naicsCodes: ['334516'], businessUnitIds: ['gen-el-mec'] }
  const scoped = { id: 'location-pending', primary_markets: ['Semiconductor'], account_segment: 'CURRENT_CLIENT', naics_assignments: [{ code: '334516' }, { code: '333242' }], commercial_business_unit_ids: ['gen-el-mec'] }
  const unknown = { id: 'unknown', primary_markets: ['Semiconductor'], account_segment: 'CURRENT_CLIENT' }
  assert.deepEqual(filterMapRecords([scoped, unknown], filters), [scoped])
  assert.deepEqual(filterMapRecords([scoped], { ...filters, businessUnitIds: ['other-bu'] }), [])
  assert.deepEqual(filterMapRecords([scoped, unknown], { ...filters, naicsCodes: [], businessUnitIds: [] }), [scoped, unknown])
  assert.equal('coordinates' in scoped, false)
})

test('coordinates accept API Decimal strings but reject unknown and non-finite values; zero is real', () => {
  for (const value of [null, {}, { latitude: null, longitude: null }, { latitude: '', longitude: '' }, { latitude: ' ', longitude: 2 }, { latitude: false, longitude: 2 }, { latitude: NaN, longitude: 2 }, { latitude: 91, longitude: 0 }]) assert.equal(validCoordinates(value), false)
  assert.equal(validCoordinates({ latitude: 0, longitude: 0 }), true)
  assert.equal(validCoordinates({ latitude: '38.01', longitude: '-98.1' }), true)
  assert.equal(haversineMiles(marker('a', 0, 0), marker('b', 0, 0)), 0)
})

test('fulfillment filters require canonical states and retain unlocated matching accounts', () => {
  const row = { primary_markets: [], account_segment: 'CURRENT_CLIENT', fulfillment_attention: { states: ['ACCEPTANCE_PENDING'] } }
  const unknown = { primary_markets: [], account_segment: 'PROSPECT' }
  const filters = { coverage: 'ALL', top100: false, industries: [], relationships: [], fulfillmentStates: ['ACCEPTANCE_PENDING'] }
  assert.deepEqual(filterMapRecords([row, unknown], filters), [row])
  assert.deepEqual(filterMapRecords([row, unknown], { ...filters, fulfillmentStates: ['MISSED_COMMITMENT'] }), [])
  assert.deepEqual(filterMapRecords([row, unknown], { ...filters, fulfillmentStates: [] }), [row, unknown])
})

test('search and capability filters apply to the full canonical result set without changing coordinates', () => {
  const records = [
    { name: 'KLA Corporation', location_name: 'KLA Milpitas', city: 'Milpitas', region: 'CA', primary_markets: ['Semiconductor'], account_segment: 'CURRENT_CLIENT', candidate_capabilities: [{ id: 'precision', name: 'Precision machining' }] },
    { name: 'Textron', location_name: 'Wichita', city: 'Wichita', region: 'KS', primary_markets: ['Aerospace'], account_segment: 'CURRENT_CLIENT', candidate_capabilities: [{ id: 'forming', name: 'Metal forming' }] },
  ]
  const base = { query: '', coverage: 'ALL', top100: false, industries: [], relationships: [] }
  assert.deepEqual(filterMapRecords(records, { ...base, query: 'milpitas' }), [records[0]])
  assert.deepEqual(filterMapRecords(records, { ...base, capabilityIds: ['forming'] }), [records[1]])
  assert.deepEqual(filterMapRecords(records, { ...base, query: 'missing' }), [])
})

test('zoom-aware clustering preserves every member and is insertion-order stable', () => {
  const input = [marker('b', 38.01, -98), marker('a', 38, -98), marker('c', 40, -80), marker('btx', 38, -98, 'btx-facility')]
  const low = markersForZoom(input, 4)
  assert.deepEqual(low, markersForZoom([...input].reverse(), 4))
  assert.deepEqual(ids(low), input.map(item => item.id).sort())
  assert.equal(low.find(item => item.kind === 'cluster').memberIds.length, 2)
  assert.equal(markersForZoom(input, 17).filter(item => item.kind === 'cluster').length, 0)
})

test('coincident sites remain selectable at high zoom without inventing positions', () => {
  const input = [marker('a', 38, -98), marker('b', 38, -98), marker('c', 38, -98)]
  const grouped = markersForZoom(input, 22)
  assert.equal(grouped.length, 1)
  assert.deepEqual(grouped[0].memberIds, ['a', 'b', 'c'])
  const selected = markersForZoom(input, 22, 'b')
  assert.equal(selected.find(item => item.id === 'b').latitude, 38)
  assert.deepEqual(ids(selected), ['a', 'b', 'c'])
})

test('clusters cross cell boundaries and the date line without moving to Greenwich', () => {
  const result = markersForZoom([marker('a', 0, 179.9), marker('b', 0, -179.9)], 4)
  assert.equal(result.length, 1)
  assert.ok(Math.abs(result[0].longitude) > 179)
  assert.ok(result[0].bounds.west > result[0].bounds.east)
})

test('layer thresholds retain current intelligence once eligible', () => {
  const input = [marker('a', 38, -98, 'intelligence'), marker('b', 38, -98, 'public-facility')]
  assert.equal(markersForZoom(input, 4).length, 0)
  assert.deepEqual(ids(markersForZoom(input, 5)), ['a'])
  assert.deepEqual(ids(markersForZoom(input, 7)), ['a', 'b'])
})
