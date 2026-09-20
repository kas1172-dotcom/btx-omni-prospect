import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const compile = source => `data:text/javascript;base64,${Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText).toString('base64')}`
const navigation = compile(await readFile(new URL('../src/app/navigation.ts', import.meta.url), 'utf8'))
const source = (await readFile(new URL('../src/features/actions/actionModel.ts', import.meta.url), 'utf8')).replace("'../../app/navigation'", JSON.stringify(navigation))
const { overdue, relativeDue, actionSource, compareDue } = await import(compile(source))

test('due dates sort ascending with absent values strictly last, even after the maximum valid date', () => {
  const items = [{ due_date: null }, { due_date: '9999-12-31' }, { due_date: '2026-09-20' }, {}]
  assert.deepEqual([...items].sort(compareDue), [items[2], items[1], items[0], items[3]])
})

test('overdue uses the injected current date, excludes closed work and respects the due day', () => {
  const action = { status: 'OPEN', due_date: '2026-09-20' }
  assert.equal(overdue(action, '2026-09-20'), false)
  assert.equal(overdue(action, '2026-09-21'), true)
  assert.equal(overdue({ ...action, status: 'COMPLETED' }, '2026-09-21'), false)
  assert.equal(overdue({ ...action, status: 'CANCELED' }, '2026-09-21'), false)
  assert.equal(overdue({ status: 'OPEN', due_date: null }, '2026-09-21'), false)
  assert.equal(relativeDue('2026-09-19', '2026-09-20'), '1d overdue')
  assert.equal(relativeDue('2026-09-20', '2026-09-20'), 'Today')
  assert.equal(relativeDue('2026-09-21', '2026-09-20'), 'Tomorrow')
})

test('task source links preserve known origins and do not invent a source for legacy tasks', () => {
  const action = { account_id: 'boeing', context_referents: [] }
  assert.equal(actionSource(action), undefined)
  assert.deepEqual(actionSource({ ...action, context_referents: [['source_screen', 'Customer 360'], ['source_route', '#/accounts/boeing']] }), { label: 'Customer 360', href: '#/accounts/boeing' })
  assert.equal(actionSource({ ...action, context_referents: [['source_route', 'javascript:alert(1)']] }), undefined)
  assert.match(actionSource({ ...action, source_suggestion_id: 'suggestion-1' }).href, /view=suggestions.*record=suggestion-1/)
  assert.match(actionSource({ ...action, context_referents: [['intelligence_event', 'event-1']] }).href, /event=event-1/)
})
