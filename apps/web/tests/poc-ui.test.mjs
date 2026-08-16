import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(new URL('../src/app/App.tsx', import.meta.url), 'utf8')
const styles = readFileSync(new URL('../src/design/app.css', import.meta.url), 'utf8')
const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const map = readFileSync(new URL('../src/features/map/Map.tsx', import.meta.url), 'utf8')
const actions = readFileSync(new URL('../src/features/actions/Actions.tsx', import.meta.url), 'utf8')

test('canonical navigation and mobile core flow are present', () => {
  for (const surface of ['Today', 'Accounts', 'Intelligence', 'Map', 'Actions', 'OmniDrawer']) assert.match(app, new RegExp(surface))
  assert.match(app, /onAccount=\{id => void select\(id\)\}/)
})

test('frontend uses only canonical Omni Prospect API routes', () => {
  for (const route of ['/accounts', '/today', '/intelligence', '/map', '/actions', '/omni']) assert.match(client, new RegExp(route))
  assert.doesNotMatch(client, /\/v1|\/v2|\/poc/)
})

test('mobile-first layout prevents horizontal overflow and exposes an Omni drawer', () => {
  assert.match(styles, /overflow-x:\s*clip/)
  assert.match(styles, /@media\(max-width:760px\)/)
  assert.match(styles, /\.omni-drawer\{width:100%/)
})

test('live Monitor observations use the canonical intelligence and map surfaces', () => {
  assert.match(app, /intelligence_signals/)
  assert.match(map, /LIVE_PUBLIC/)
  assert.match(map, /No linked signals have map coordinates/)
})

test('map and action interactions remain touch-accessible and confirmation-safe', () => {
  assert.match(map, /Layer controls/)
  assert.match(map, /Account quick view/)
  assert.match(actions, /Confirm CRM execution/)
  assert.match(actions, /Preview & confirm CRM action/)
})
