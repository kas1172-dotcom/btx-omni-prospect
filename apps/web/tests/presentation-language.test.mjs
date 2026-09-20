import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const presentation = read('../src/components/presentation.ts')
const intelligence = read('../src/features/intelligence/Intelligence.tsx')
const model = read('../src/components/signalBriefModel.ts')
const communications = read('../src/features/communications/Communications.tsx')
const monitor = read('../src/features/monitor/Monitor.tsx')
const relationships = read('../src/features/accounts/RankedRelationships.tsx')
const tokens = read('../src/design/tokens.css')

test('shared presentation language has controlled labels and a safe unknown fallback', () => {
  for (const text of ['Ready for delivery confirmation', 'Needs validation', 'Evidence resolved for review', 'Strategic partnership', 'Assigned seller', 'Status available in supporting details']) assert.match(presentation, new RegExp(text))
  assert.match(presentation, /identifierPattern/)
  assert.match(presentation, /actorDisplayName/)
  assert.match(presentation, /safeRecordTitle/)
})

test('Intelligence prefers persisted assessments and distinguishes incomplete analysis', () => {
  assert.match(model, /signal\.business_briefing \?\?/)
  assert.match(model, /analysis_status: 'PENDING_ANALYSIS'/)
  assert.match(intelligence, /const complete = brief\.analysis_status === "READY"/)
  assert.match(intelligence, /Research direction · not yet assessed/)
  assert.match(intelligence, /brief\.why_it_may_matter/)
  assert.match(intelligence, /\[\.\.\.curated, \.\.\.savedRecent, \.\.\.current\]/)
  assert.doesNotMatch(intelligence, /linked to a canonical Customer or Prospect/)
})

test('primary communication and relationship labels do not expose actor or edge IDs', () => {
  assert.match(communications, /actorDisplayName\(selected\.created_by, principal\)/)
  assert.match(communications, /actorDisplayName\(event\.actor_id, principal\)/)
  assert.match(communications, /Actor ID \$\{event\.actor_id\}/)
  assert.doesNotMatch(relationships, /aria-label=\{`Inspect \$\{label\(item\.predicate\)\} · \$\{item\.id\}`\}/)
  assert.match(relationships, /Supporting record \{index \+ 1\}/)
})

test('environment copy is singular and provenance details remain available', () => {
  assert.match(monitor, /Administrator operations/)
  assert.doesNotMatch(monitor, /Curated POC|NOT LIVE INGESTION/)
  assert.match(monitor, /Retained operational evidence/)
})

test('muted text token exceeds the audited failing value', () => {
  assert.match(tokens, /--text-tertiary: #667181/)
  assert.doesNotMatch(tokens, /--text-tertiary: #737d8c/)
})
