import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const attentionSource = await readFile(new URL('../src/components/attentionModel.ts', import.meta.url), 'utf8')
const attentionModule = ts.transpileModule(attentionSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const attentionUrl = `data:text/javascript;base64,${Buffer.from(attentionModule).toString('base64')}`
const modelSource = await readFile(new URL('../src/features/today/todayModel.ts', import.meta.url), 'utf8')
const modelModule = ts.transpileModule(modelSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
  .replace("from '../../components/attentionModel'", `from '${attentionUrl}'`)
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
    { id: 'internal-high', kind: 'COMMERCIAL_REVIEW', severity: 'HIGH', reason: '', evidence_ids: [], data_mode: 'SAMPLE' },
    { id: 'internal-medium', kind: 'COMMERCIAL_REVIEW', severity: 'MEDIUM', reason: '', evidence_ids: [], data_mode: 'SAMPLE' },
    { id: 'public-high', kind: 'PUBLIC_SIGNAL', reason: '', evidence_ids: [], data_mode: 'LIVE_PUBLIC', signal_brief: { analysis_status: 'READY', priority_eligible: true } },
  ]
  assert.equal(items.filter(isHighImportance).length, items.filter(item => attentionFor(item) === 'HIGH').length)
  assert.equal(items.filter(isHighImportance).length, 2)
})

test('localDateLabel leaves date-only calendar values unshifted', () => {
  assert.match(localDateLabel('2026-09-20'), /Sep 20, 2026/)
  assert.equal(localDateLabel(undefined), undefined)
})
