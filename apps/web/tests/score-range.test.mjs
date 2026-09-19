import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/components/scoreSummaryModel.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText
const { scoreValue, commercialDecisionSummary } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

test('partial range is explicitly incomplete, never a midpoint or inflated point score', () => {
  assert.equal(scoreValue(null, { low: '22.00', high: '100.00' }), '22–100/100 · incomplete')
  assert.equal(scoreValue('0', { low: 0, high: 0 }), '0')
  assert.equal(scoreValue(null), null)
  assert.equal(scoreValue(null, { low: 101, high: 100 }), null)
})

test('ineligible and blocked decisions cannot acquire a displayed score from a range', () => {
  const decision = { family: 'pwin', score: null, score_range: { low: 40, high: 100 }, factors: [], data_coverage: { missing_fields: [] } }
  for (const [status, label] of [['INELIGIBLE', 'Not applicable yet'], ['BLOCKED', 'Blocked']]) {
    const summary = commercialDecisionSummary({ ...decision, status }, 'Customer')
    assert.equal(summary.value, label)
    assert.equal(summary.numericValue, null)
  }
  assert.equal(commercialDecisionSummary({ ...decision, status: 'INSUFFICIENT_EVIDENCE' }, 'Customer').value, '40–100/100 · incomplete')
})

test('each score family retains its agreed primary display', () => {
  const decision = { score: '72.50', status: 'AVAILABLE', factors: [], data_coverage: { missing_fields: [] } }
  const display = (family, extra = {}) => commercialDecisionSummary({ ...decision, family, ...extra }, 'Customer')
  assert.equal(display('customer_health').value, 'Healthy')
  assert.equal(display('delivery_feasibility').value, 'B')
  assert.equal(display('signal_confidence').value, 'High')
  assert.equal(display('internal_commercial_risk').value, '72.50')
  assert.equal(display('action_priority', { score: null, priority_rank: 3 }).value, 'Queue position 3')
  assert.equal(display('customer_health').numericValue, '72.50')
})
