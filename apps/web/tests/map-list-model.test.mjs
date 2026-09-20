import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/features/map/mapListModel.ts', import.meta.url), 'utf8').then(value => value.replace("import type { MapMarker } from './mapModel'", ''))
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { synchronizedMapSites, synchronizedSiteCount } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const mapSource = await readFile(new URL('../src/features/map/mapModel.ts', import.meta.url), 'utf8')
const mapOutput = ts.transpileModule(mapSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const { buildMapMarkers, filterMapRecords } = await import(`data:text/javascript;base64,${Buffer.from(mapOutput).toString('base64')}`)

test('map and list consume the same canonical site array and count', () => {
  const sites = [{ id: 'a', kind: 'customer' }, { id: 'b', kind: 'btx-facility' }]
  assert.strictEqual(synchronizedMapSites(sites), sites)
  assert.equal(synchronizedSiteCount(sites), sites.length)
})

test('presentation clusters never become duplicate list rows', () => {
  const sites = [{ id: 'a', kind: 'customer' }, { id: 'cluster:a|b', kind: 'cluster' }, { id: 'b', kind: 'prospect' }]
  assert.deepEqual(synchronizedMapSites(sites).map(item => item.id), ['a', 'b'])
  assert.equal(synchronizedSiteCount(sites), 2)
})

test('Top 100 SAMPLE membership keeps filter, marker, and list counts equal', () => {
  const record = (id, top100) => ({ id, account_id: id, facility_id: `${id}-site`, name: id, location_name: `${id} site`, city: 'Sample City', region: 'KS', country: 'US', is_rich_scenario: false, btx_top_100: top100, primary_markets: ['Aerospace'], account_segment: 'CURRENT_CLIENT', coordinates: { latitude: 38, longitude: -97 } })
  const records = [record('member-a', true), record('not-member', false), record('member-b', true)]
  const filters = { query: '', coverage: 'ALL', top100: true, industries: [], relationships: [] }
  const filtered = filterMapRecords(records, filters)
  const markers = buildMapMarkers(filtered, [], [], [], ['customers', 'prospects'])
  assert.equal(filtered.length, 2)
  assert.equal(markers.length, filtered.length)
  assert.equal(synchronizedSiteCount(markers), markers.length)
})
