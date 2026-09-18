import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const marketSource = await readFile(new URL('../src/features/intelligence/marketPresentation.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(marketSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { marketDecision, comparisonCompatibility } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const market = readFileSync(new URL('../src/features/intelligence/MarketIntelligence.tsx', import.meta.url), 'utf8')
const map = readFileSync(new URL('../src/features/map/Map.tsx', import.meta.url), 'utf8')
const filters = readFileSync(new URL('../src/features/map/MapFilterPanel.tsx', import.meta.url), 'utf8')
const itinerary = readFileSync(new URL('../src/features/map/ItineraryPlanner.tsx', import.meta.url), 'utf8')
const tokens = readFileSync(new URL('../src/design/tokens.css', import.meta.url), 'utf8')

const metadata = { title: 'Industrial production', unit: 'Index', index_base: '2017=100', frequency: 'Monthly', geography: 'National United States', seasonal_adjustment: 'Seasonally adjusted', limitation: 'No regional or account dimension.' }

test('market decision language remains series-specific and refuses account or regional claims', () => {
  const decision = marketDecision({ metadata, points: [{ period: '2026-06', value: '100' }, { period: '2026-07', value: '102' }] }, 'LEVEL')
  assert.equal(decision.direction, 'Higher than the prior month')
  assert.equal(decision.geography, 'National United States')
  assert.match(decision.commercialMeaning, /does not establish an account order, regional demand, facility activity or BTX capacity/)
})

test('market comparison rejects incompatible unit, cadence or geography without normalization', () => {
  assert.equal(comparisonCompatibility(metadata, { ...metadata, unit: 'Dollars' }).compatible, false)
  assert.match(comparisonCompatibility(metadata, { ...metadata, geography: 'Regional' }).reason, /geography/)
  assert.equal(comparisonCompatibility(metadata, { ...metadata }).compatible, true)
})

test('Wave 4 surfaces use shared state grammar, bounded selectors and honest route language', () => {
  assert.match(market, /StatusMessage state="refreshing"/)
  assert.match(market, /Full observation table/)
  assert.match(market, /Comparison unavailable/)
  assert.match(filters, /HighCardinalitySelector/)
  assert.match(filters, /Candidate BTX capability/)
  assert.match(map, /Location pending/)
  assert.match(map, /Add to shortlist/)
  assert.match(map, /Ask Omni/)
  assert.match(itinerary, /Route timing unavailable/)
  assert.match(itinerary, /Complete street address unavailable/)
  assert.doesNotMatch(itinerary.split('Route-provider details')[0], /Origin latitude|Origin longitude/)
})

test('semantic accents remain restrained, named and redundant with text', () => {
  for (const name of ['selected', 'supported', 'validation', 'risk', 'stale', 'unavailable', 'public', 'internal']) assert.match(tokens, new RegExp(`--semantic-${name}:`))
  assert.match(tokens, /--semantic-risk: #b42318/)
})
