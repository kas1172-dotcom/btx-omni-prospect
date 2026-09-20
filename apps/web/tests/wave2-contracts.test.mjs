import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const today = read('../src/features/today/Today.tsx')
const actions = read('../src/features/actions/Actions.tsx')
const suggestions = read('../src/features/actions/SuggestionList.tsx')
const selector = read('../src/components/HighCardinalitySelector.tsx')
const memory = read('../src/features/settings/OmniMemory.tsx')
const ui = read('../src/components/UI.tsx')

test('Wave 2 queues bound rendering after whole-result filtering and stable sorting', () => {
  assert.match(today, /allPriority\.slice\(0, 3\)\.map/)
  assert.match(today, /pageSlice\(sortedPriority/)
  assert.match(today, /missingLastDate/)
  assert.match(actions, /pageSlice\(visible/)
  assert.match(actions, /compareDue\(a, b\)/)
  assert.match(actions, /a\.created_at\.localeCompare\(b\.created_at\)/)
  assert.match(suggestions, /pageSlice\(filtered/)
  assert.match(suggestions, /Each remains separate because its evidence or source revision may differ/)
})

test('Wave 2 selectors are bounded, identity preserving and explicit about zero matches', () => {
  assert.match(selector, /MAX_RESULTS = 12/)
  assert.match(selector, /role="combobox"/)
  assert.match(selector, /role="listbox"/)
  assert.match(selector, /No choices match this filter/)
  assert.match(memory, /Global — all my account contexts/)
  assert.doesNotMatch(memory, /account\.id\}\<\/option\>/)
})

test('shared resource grammar distinguishes the governed Wave 2 states', () => {
  for (const state of ['loading', 'empty', 'filtered-empty', 'not-applicable', 'partial', 'stale', 'unavailable', 'permission', 'error', 'refreshing']) assert.match(ui, new RegExp(`'${state}'`))
  assert.match(memory, /Last-good preferences remain visible/)
  assert.match(memory, /Retry memories/)
})
