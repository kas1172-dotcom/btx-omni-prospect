import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/features/accounts/RankedRelationships.tsx', import.meta.url), 'utf8')

test('imported network contacts stay unvalidated and expose bounded inspector filters', () => {
  assert.match(source, /contacts ·.*senior.*source_people.*unvalidated/)
  assert.match(source, /Contacts on this route · unvalidated/)
  assert.match(source, />Function<select/)
  assert.match(source, />Seniority<select/)
  assert.match(source, />Recency<select/)
  assert.match(source, /provenance_label/)
  assert.match(source, /resolution_method/)
  assert.match(source, /width="184" height="136"/)
  assert.match(source, /external_contact: 'External contact'/)
  assert.match(source, /governed_name_exact: 'Exact governed name'/)
  assert.match(source, /governed_name_normalized: 'Normalized governed name'/)
})

test('transient breakpoint events cannot leave loading active without a request', () => {
  const mediaEffect = source.split("media.addEventListener('change', update)")[0].split('const update = () =>')[1]
  assert.ok(mediaEffect)
  assert.doesNotMatch(mediaEffect, /setPending/)
  assert.match(source, /queueMicrotask\(\(\) => \{ if \(!controller.signal.aborted\) setPending\(true\) \}\)/)
})
