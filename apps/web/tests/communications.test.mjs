import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const source = read('../src/features/communications/communicationModel.ts')
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText
const { defaultView, viewCounts, inView, canSend, workflowSteps } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)
const ui = read('../src/features/communications/Communications.tsx')
const app = read('../src/app/App.tsx')
const seller = { user_id: 'seller-a', role: 'SALESPERSON', display_name: 'Seller A' }
const manager = { user_id: 'manager-a', role: 'MANAGER', display_name: 'Manager A' }
const draft = { id: 'draft-a', created_by: seller.user_id, status: 'DRAFT', approval_status: 'PENDING', recipients: [] }
const delivery = { state: 'NOT_CONFIGURED', label: 'Delivery not configured' }

test('queue counts and role defaults use saved ownership and review state', () => {
  const items = [draft, { ...draft, created_by: manager.user_id },
    { ...draft, status: 'READY', approval_status: 'APPROVED' },
    { ...draft, approval_status: 'REJECTED', created_by: 'another-seller' },
    { ...draft, status: 'CANCELED' }]
  assert.equal(defaultView(manager), 'Needs review')
  assert.equal(defaultView(seller), 'Mine')
  assert.equal(defaultView(), 'Mine')
  assert.deepEqual(viewCounts(items, seller), { All: 5, Mine: 3, 'Needs review': 2, Approved: 1, Rejected: 1 })
  assert.equal(inView(draft, 'Mine'), false)
  assert.equal(inView(items[4], 'Needs review', manager), false)
  assert.deepEqual(viewCounts([], seller), { All: 0, Mine: 0, 'Needs review': 0, Approved: 0, Rejected: 0 })
})

test('delivery fails closed despite approval and a recipient', () => {
  const approved = { ...draft, status: 'READY', approval_status: 'APPROVED', recipients: ['test@example.invalid'] }
  for (const state of [delivery, undefined, { state: 'UNKNOWN' }, { state: 'UNAVAILABLE' }]) assert.equal(canSend(approved, state), false)
  const configured = { state: 'CONFIGURED' }
  assert.equal(canSend(approved, configured), true)
  assert.equal(canSend({ ...approved, recipients: [] }, configured), false)
  assert.equal(canSend({ ...approved, approval_status: 'PENDING' }, configured), false)
  assert.equal(canSend({ ...approved, status: 'SENT' }, configured), false)
  assert.match(ui, /disabled=\{listState !== 'loaded' \|\| !canSend\(selected, delivery\)\}/)
  assert.match(ui, /Delivery is not configured for this environment/)
  assert.match(app, /setCommunicationDelivery\(value\.delivery\)/)
  assert.doesNotMatch(ui, /<StatusBadge value="NOT_CONFIGURED"/)
})

test('workflow never marks approval or delivery complete from pending or ready alone', () => {
  assert.deepEqual(workflowSteps(draft, delivery).map(step => step.complete), [true, false, false, false])
  const rejected = workflowSteps({ ...draft, approval_status: 'REJECTED' }, delivery)
  assert.equal(rejected[1].complete, true)
  assert.equal(rejected[2].complete, false)
  const approved = workflowSteps({ ...draft, status: 'READY', approval_status: 'APPROVED' }, delivery)
  assert.equal(approved[3].detail, 'Unavailable')
  assert.equal(approved[3].complete, false)
  assert.equal(workflowSteps({ ...draft, status: 'SENT', approval_status: 'APPROVED' }, delivery)[3].complete, true)
})

test('context preserves missing trigger and evidence without inventing source details', () => {
  assert.match(ui, /draft\.trigger \|\| "No trigger recorded"/)
  assert.match(ui, /draft\.evidence_ids\.length[\s\S]*: "No evidence linked"/)
  assert.match(ui, /contact\?\.provenance\?\.last_verified_at &&/)
  assert.match(ui, /Public contact · source details unavailable/)
  assert.equal((ui.match(/<DraftContext /g) ?? []).length, 2)
  assert.equal((ui.match(/\.account\(accountId, controller.signal\)/g) ?? []).length, 1)
})

test('editor warns about removing approval while retaining explicit versioned save', () => {
  assert.match(ui, /baseDraft\?\.approval_status === "APPROVED" \|\| savedComparison\?\.approval_status === "APPROVED"/)
  assert.match(ui, /Saving changes will remove approval and require review again\./)
  assert.match(ui, /Unsaved changes/)
  assert.match(ui, /expected_version: baseDraft!\.version/)
  const assist = ui.slice(ui.indexOf('const assist = async'), ui.indexOf('const refreshSaved = async'))
  assert.match(assist, /setSubject\(result\.proposal\.subject\)/)
  assert.doesNotMatch(assist, /createCommunication|editCommunication|onSaved/)
  assert.match(ui, /principal\?\.role === "MANAGER"/)
})

test('history loads by selected version and shows latest five without a disclosure gate', () => {
  assert.match(ui, /if \(!historyId \|\| historyVersion === undefined\) return/)
  assert.match(ui, /loadedHistory\?\.version === historyVersion/)
  assert.match(ui, /history\.slice\(0, 5\)/)
  assert.match(ui, /No history recorded/)
  assert.match(ui, /History could not be loaded/)
  assert.match(ui, /event\.key === 'ArrowDown'/)
  assert.match(ui, /event\.key === 'ArrowUp'/)
  assert.match(ui, /event\.key === 'Enter'/)
  assert.match(ui, /role="status" aria-live="polite"/)
})
