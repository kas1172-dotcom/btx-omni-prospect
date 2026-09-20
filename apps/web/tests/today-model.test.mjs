import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const modelSource = await readFile(new URL('../src/features/today/todayModel.ts', import.meta.url), 'utf8')
const modelModule = ts.transpileModule(modelSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const { attentionFor, greetingFor, isHighImportance, localDateLabel } = await import(`data:text/javascript;base64,${Buffer.from(modelModule).toString('base64')}`)

test('greetingFor uses viewer local-hour boundaries', () => {
  assert.equal(greetingFor(new Date(2026, 8, 20, 4, 59)), 'Good evening')
  assert.equal(greetingFor(new Date(2026, 8, 20, 5, 0)), 'Good morning')
  assert.equal(greetingFor(new Date(2026, 8, 20, 11, 59)), 'Good morning')
  assert.equal(greetingFor(new Date(2026, 8, 20, 12, 0)), 'Good afternoon')
  assert.equal(greetingFor(new Date(2026, 8, 20, 16, 59)), 'Good afternoon')
  assert.equal(greetingFor(new Date(2026, 8, 20, 17, 0)), 'Good evening')
})

test('one high-importance predicate drives badge tiers and header count', () => {
  const items = [
    { id: 'internal-high', kind: 'COMMERCIAL_REVIEW', high_importance: true, severity: 'HIGH' },
    { id: 'internal-medium', kind: 'COMMERCIAL_REVIEW', high_importance: false, severity: 'HIGH' },
    { id: 'public-high', kind: 'PUBLIC_SIGNAL', high_importance: true },
    { id: 'legacy', kind: 'PUBLIC_SIGNAL', signal_brief: { analysis_status: 'READY', priority_eligible: true } },
  ]
  assert.equal(items.filter(isHighImportance).length, items.filter(item => attentionFor(item) === 'HIGH').length)
  assert.equal(items.filter(isHighImportance).length, 2)
  assert.equal(attentionFor(items[1]), 'MEDIUM')
  assert.equal(attentionFor(items[3]), 'UNAVAILABLE')
})

test('localDateLabel leaves date-only calendar values unshifted', () => {
  assert.match(localDateLabel('2026-09-20'), /Sep 20, 2026/)
  assert.equal(localDateLabel(undefined), undefined)
})
