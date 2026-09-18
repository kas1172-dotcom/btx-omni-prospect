import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const accounts = read('../src/features/accounts/Accounts.tsx')
const relationships = read('../src/features/accounts/RankedRelationships.tsx')
const language = read('../src/components/relationshipPresentation.ts')
const scores = read('../src/components/ScoreSummary.tsx')
const scoreModels = read('../src/components/scoreSummaryModel.ts')
const omni = read('../src/components/OmniDrawer.tsx')

test('Organization 360 leads with the seller decision and gates the full graph', () => {
  for (const label of ['What changed', 'Why it matters', 'Material uncertainty', 'Governed next action']) assert.match(accounts, new RegExp(label))
  assert.match(accounts, /Open full Relationship Intelligence workspace/)
  assert.match(accounts, /subview === 'relationships'/)
  assert.match(accounts, /Current customer status does not establish participation in this pursuit/)
})

test('relationship views share seller language and protect hypotheses', () => {
  for (const label of ['Recorded relationship', 'Possible route to investigate', 'Needs validation', 'Not currently actionable']) assert.match(language, new RegExp(label))
  assert.match(language, /Recorded role affiliation/)
  assert.match(relationships, /relationshipPredicateLabel/)
  assert.match(relationships, /relationshipEvidenceLabel/)
  assert.doesNotMatch(relationships, /<small>\{item\.id\}/)
})

test('shared score summary separates decision meaning, unavailable values and coverage', () => {
  assert.match(scores, /Decision supported:/)
  assert.match(scores, /Data Coverage/)
  assert.match(scores, /Coverage describes completeness and never raises this decision score/)
  assert.match(scores, /Missing required inputs/)
  assert.match(scores, /Formula, inputs and supporting evidence/)
  assert.match(scores, /value == null.*Unavailable/)
  assert.match(scoreModels, /commercialDecisionSummary/)
})

test('provider fallback stays behind a secondary Omni disclosure', () => {
  assert.match(omni, /Disclosure title="Answer delivery details"/)
  assert.ok(omni.indexOf('Disclosure title="Answer delivery details"') < omni.indexOf('<small>{response.context_used?.synthesis_validation'))
})
