import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const attention = read('../src/components/AttentionBadge.tsx')
const attentionModel = read('../src/components/attentionModel.ts')
const signal = read('../src/components/SignalBriefCard.tsx')
const accounts = read('../src/features/accounts/Accounts.tsx')
const intelligence = read('../src/features/intelligence/Intelligence.tsx')
const ui = read('../src/components/UI.tsx')

test('attention uses deterministic assessment outcomes and labeled high medium low states', () => {
  assert.match(attentionModel, /brief\.priority_eligible.*'HIGH'/s)
  assert.match(attentionModel, /REVIEW_REQUIRED.*'MEDIUM'/s)
  assert.match(attentionModel, /INFORMATIONAL.*'LOW'/s)
  for (const label of ['High importance', 'Medium importance', 'Low importance', 'Importance not yet determined']) assert.match(attention, new RegExp(label))
  assert.match(ui, /'LIVE_PUBLIC', 'LOW'/)
})

test('decision summaries separate change impact uncertainty and next decision', () => {
  for (const label of ['What changed', 'Why it may matter', 'Next decision', 'still unconfirmed']) assert.match(signal, new RegExp(label, 'i'))
  assert.match(accounts, /persistedBrief\?\.analysis_status === 'READY' \? persistedBrief : undefined/)
  assert.doesNotMatch(accounts, /curatedSignalBrief\(sourceSignal/)
  assert.match(accounts, /<ProfileOverview detail=\{detail\} location=\{location\}/)
  assert.doesNotMatch(accounts, /className="account-decision-zone"/)
  assert.doesNotMatch(accounts, /No material uncertainty is currently recorded/)
  assert.match(intelligence, /Research direction · not yet assessed/)
  assert.match(intelligence, /brief\.why_it_may_matter/)
  assert.doesNotMatch(intelligence, /The commercial implication has not yet been established/)
})

test('Intelligence owns the research library while Today exclusively owns priority queues', () => {
  assert.doesNotMatch(intelligence, /Today's Priority Signals|title: "Action priorities"|title: "Needs validation"/)
  assert.match(intelligence, /title: "Available intelligence"/)
  assert.match(intelligence, /title: "Collection freshness"/)
  assert.match(intelligence, /saved_recent_signal_briefs/)
  assert.match(intelligence, /Sort: Importance/)
  assert.doesNotMatch(intelligence, /backend priority|rank=\{/)
})
