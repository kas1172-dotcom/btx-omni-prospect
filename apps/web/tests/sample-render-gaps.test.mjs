// UI render-check fixes: smoke-contract coverage for relationship safety, bands, and provenance.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const overview = read('../src/features/accounts/ProfileOverview.tsx')
const portfolio = read('../src/features/accounts/Portfolio.tsx')
const opportunity = read('../src/features/opportunities/OpportunityDetail.tsx')
const evidence = read('../src/features/accounts/CommercialEvidence.tsx')

test('SAMPLE customer label is supplied by the account API, not inferred in the UI', () => {
  assert.match(read('../src/features/accounts/Accounts.tsx'), /organization\.relationship_label/)
})

test('prospect access renders the API display label, not the raw relationship enum', () => {
  assert.match(overview, /Access level: \{detail\.public_relationship\?\.label/)
  assert.doesNotMatch(overview, /Access level: \{detail\.public_relationship\?\.state/)
})

test('parallel prospect pursuit evidence retains its account-scoped drawer', () => {
  assert.match(opportunity, /<CommercialEvidence key=\{row\.opportunity_id\} accountId=\{row\.account_id\}/)
  assert.match(evidence, /api\.commercialEvidence\(accountId, recordId/)
})

test('customer health and risk show scorer-supplied bands', () => {
  assert.match(overview, /bandLabel\(profile\.health_band\)/)
  assert.match(overview, /bandLabel\(profile\.internal_commercial_risk\.band\)/)
})

test('pursuit evidence summaries expose numeric result and band or grade', () => {
  assert.match(opportunity, /Calculated result \$\{d\.score\}\/100 · Grade/)
  assert.match(opportunity, /Calculated result \$\{d\.score\}\/100 · Band/)
})

test('Prospect Fit shows its API band next to the percentage', () => {
  assert.match(overview, /bandLabel\(detail\.prospect_fit\.band\)/)
})

test('portfolio tooltip distinguishes public identity, commercial record, and modeled Fit', () => {
  assert.match(portfolio, /Public identity:.*Commercial record:.*Prospect Fit: SAMPLE modeled/)
  assert.match(portfolio, /title=\{provenanceTooltip\(row\)\}/)
})
