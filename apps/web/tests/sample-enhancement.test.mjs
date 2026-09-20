import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const output = ts.transpileModule(read('../src/components/scoreSummaryModel.ts'), { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText
const { familyValue } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

test('golden delivery and incomplete cases retain their governed primary display', () => {
  assert.equal(familyValue({ family: 'delivery_feasibility', score: 72.5, status: 'SCORED' }), 'B')
  assert.equal(familyValue({ family: 'delivery_feasibility', score: null, weighted_score: 78.75, status: 'BLOCKED', score_range: { low: 78.75, high: 78.75 } }), 'Blocked')
  assert.equal(familyValue({ family: 'pwin', score: null, status: 'INSUFFICIENT_EVIDENCE', score_range: { low: 68, high: 83 } }), '68–83/100 · incomplete')
  assert.equal(familyValue({ family: 'pwin', score: 66.25, status: 'SCORED' }), 66.25)
})

test('directory and map expose the same three explicit partnership scopes', () => {
  for (const path of ['../src/features/accounts/Portfolio.tsx', '../src/features/map/MapFilterPanel.tsx']) {
    const source = read(path)
    for (const label of ['All (Customers &amp; Prospects)', 'Exclude strategic partnerships', 'Strategic partnerships only']) assert.ok(source.includes(label))
  }
})

test('sample narratives and calculation traces stay visible and labeled', () => {
  assert.ok(read('../src/features/accounts/Accounts.tsx').includes('SAMPLE scenario evidence'))
  assert.ok(read('../src/features/map/MapAccountDetails.tsx').includes('SAMPLE commercial narrative and calculated evidence'))
  const decisions = read('../src/features/accounts/CommercialDecisions.tsx')
  assert.ok(decisions.includes('weighted_band: decision.weighted_band'))
  assert.ok(decisions.includes('scoreValue(null, result.overall_customer_risk.score_range)'))
  assert.ok(read('../src/features/intelligence/MarketIntelligence.tsx').includes('not customer evidence'))
})
