import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(new URL('../src/app/App.tsx', import.meta.url), 'utf8')
const styles = readFileSync(new URL('../src/design/app.css', import.meta.url), 'utf8')
const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const map = readFileSync(new URL('../src/features/map/Map.tsx', import.meta.url), 'utf8')
const mapCanvas = readFileSync(new URL('../src/features/map/MapCanvas.tsx', import.meta.url), 'utf8')
const actions = readFileSync(new URL('../src/features/actions/Actions.tsx', import.meta.url), 'utf8')
const accounts = readFileSync(new URL('../src/features/accounts/Accounts.tsx', import.meta.url), 'utf8')
const intelligence = readFileSync(new URL('../src/features/intelligence/Intelligence.tsx', import.meta.url), 'utf8')
const today = readFileSync(new URL('../src/features/today/Today.tsx', import.meta.url), 'utf8')
const monitor = readFileSync(new URL('../src/features/monitor/Monitor.tsx', import.meta.url), 'utf8')

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
  assert.match(app, /map\.intelligence/)
  assert.match(map, /geographically linked intelligence/)
  assert.match(map, /No current intelligence event has verified event or canonical-facility coordinates/)
  assert.match(app, /Promise\.all\(\[api\.accounts\(\), api\.today\(\), api\.intelligence\(\), api\.map\(\), api\.actions\(\)\]\)/)
  assert.match(app, /void api\.monitor\(\)\.then\(setMonitor\)\.catch/)
})

test('Account 360 distinguishes public evidence from simulated BTX context', () => {
  assert.match(accounts, /Public professional contact research/)
  assert.match(accounts, /Simulated BTX commercial context/)
  assert.match(accounts, /Account Attractiveness · POC simulation/)
  assert.match(accounts, /Coverage/)
  assert.match(accounts, /Curated scenarios/)
})

test('Omni provides session-only deterministic chat with optional context and safe keyboard behavior', () => {
  const drawer = readFileSync(new URL('../src/components/OmniDrawer.tsx', import.meta.url), 'utf8')
  assert.match(drawer, /No account selected/)
  assert.match(drawer, /Clear/)
  assert.match(drawer, /What should I review today\?/)
  assert.match(drawer, /Shift\+Enter for a new line/)
  assert.match(drawer, /session_account_id/)
  assert.match(drawer, /citation_links/)
  assert.match(drawer, /Deterministic fallback—not model-generated advice/)
  assert.match(drawer, /cannot write to CRM/)
  assert.match(drawer, /aria-modal="true"/)
})

test('map and action interactions remain touch-accessible and confirmation-safe', () => {
  assert.match(map, /Map controls/)
  assert.match(map, /Map layers/)
  assert.match(map, /Clear filters/)
  assert.match(map, /Account segment/)
  assert.match(map, /Current clients/)
  assert.match(map, /Unknown \/ no internal history/)
  assert.match(map, /account_segment/)
  assert.doesNotMatch(map, /Current customers|Top 100/)
  assert.match(map, /Account quick view/)
  assert.match(mapCanvas, /maplibregl\.Map/)
  assert.match(mapCanvas, /clusterRadius/)
  assert.match(mapCanvas, /account-clusters/)
  assert.match(mapCanvas, /setData/)
  assert.match(mapCanvas, /maplibregl\.Marker/)
  assert.match(mapCanvas, /queryRenderedFeatures/)
  assert.match(mapCanvas, /map-dom-marker/)
  assert.match(actions, /Confirm demo CRM execution/)
  assert.match(actions, /Preview demo CRM action/)
  assert.match(mapCanvas, /Map unavailable/)
  assert.match(mapCanvas, /tile\.openstreetmap\.org/)
  assert.match(map, /onAccountSelect=\{selectAccount\}/)
  assert.match(map, /item\.coordinates/)
  assert.match(actions, /Development-only user identity/)
})

test('Actions workbench prioritizes, filters, and keeps evidence and demo CRM confirmation separate', () => {
  assert.match(actions, /Priority inbox/)
  assert.match(actions, /Filter by priority/)
  assert.match(actions, /Filter by industry/)
  assert.match(actions, /Filter by status/)
  assert.match(actions, /Evidence and provenance/)
  assert.match(actions, /href=\{signal\.source_url\}/)
  assert.match(actions, /Public event:/)
  assert.match(actions, /Preview demo CRM action/)
  assert.match(actions, /Continue to explicit confirmation/)
  assert.match(actions, /SIMULATED BTX WORKFLOW/)
  assert.match(actions, /priorityRank/)
})

test('Intelligence distinguishes browser validation from publisher-blocked source checks', () => {
  assert.match(intelligence, /AUTOMATION_BLOCKED/)
  assert.match(intelligence, /Publisher controls blocked automated validation/)
  assert.match(intelligence, /BROWSER_VERIFIED/)
  assert.match(intelligence, /source_validation_state/)
  assert.match(intelligence, /timeZone: 'UTC'/)
})

test('Intelligence sends canonical selected event context to the shared Omni request and clears it on navigation', () => {
  const drawer = readFileSync(new URL('../src/components/OmniDrawer.tsx', import.meta.url), 'utf8')
  assert.match(intelligence, /onEventSelect/)
  assert.match(intelligence, /selectEvent\(signal\.id\)/)
  assert.match(intelligence, /aria-pressed=\{selectedEventId === signal\.id\}/)
  assert.match(app, /selectedEventId/)
  assert.match(app, /selected_event_id: surface === 'intelligence' \? selectedEventId : undefined/)
  assert.match(app, /onClick=\{\(\) => navigate\(id\)\}/)
  assert.match(drawer, /\{ \.\.\.context, session_account_id/)
  assert.match(drawer, /conversationReferent/)
  assert.match(drawer, /conversation_referent: conversationReferent/)
  assert.match(drawer, /setConversationReferent\(response\.conversation_referent/)
})

test('Map selection sends canonical account and facility context without inventing BTX account identity', () => {
  assert.match(map, /selectAccount = \(accountId: string\)/)
  assert.match(map, /selectFacility = \(facilityId: string, accountId\?: string\)/)
  assert.match(map, /selectFacility\(location\.facility_id, location\.account_id\)/)
  assert.match(map, /selectFacility\(facility\.facility_id\)/)
  assert.match(mapCanvas, /facilityId: item\.facility_id \?\? ''/)
  assert.match(mapCanvas, /onFacilitySelectRef\.current\(facilityId, feature\.accountId \|\| undefined\)/)
  assert.match(app, /selectedMapAccountId/)
  assert.match(app, /selectedMapFacilityId/)
  assert.match(app, /selected_facility_id: surface === 'map' \? selectedMapFacilityId : undefined/)
  assert.match(app, /onClick=\{\(\) => navigate\(id\)\}/)
})

test('Actions sends the selected canonical work-item ID without leaking other passive selections', () => {
  assert.match(actions, /onActionSelect/)
  assert.match(actions, /onActionSelect\(selected\?\.id\)/)
  assert.match(actions, /setSelectedId\(item\.id\)/)
  assert.match(app, /selectedActionId/)
  assert.match(app, /selected_action_id: surface === 'actions' \? selectedActionId : undefined/)
  assert.match(app, /onClick=\{\(\) => navigate\(id\)\}/)
})

test('list surfaces publish only their current filters and bounded canonical visible IDs to Omni', () => {
  assert.match(accounts, /account_scope: 'RICH'/)
  assert.match(accounts, /market: industry/)
  assert.match(accounts, /shown\.slice\(0, 50\)\.map\(account => account\.id\)/)
  assert.match(accounts, /onOmniContext\(\{ active_filters: Object\.keys\(activeFilters\)\.length \? activeFilters : undefined, visible_record_ids: visibleRecordIds \}\)/)
  assert.match(intelligence, /signals\.slice\(0, 50\)\.map\(signal => signal\.id\)/)
  assert.match(intelligence, /onOmniContext\(\{ visible_record_ids: visibleRecordIds \}\)/)
  assert.match(actions, /action_status: 'ACTIVE'/)
  assert.match(actions, /market: industry/)
  assert.match(actions, /visible\.slice\(0, 50\)\.map\(item => item\.id\)/)
  assert.match(actions, /onOmniContext\(\{ active_filters: Object\.keys\(activeFilters\)\.length \? activeFilters : undefined, visible_record_ids: visibleRecordIds \}\)/)
  assert.match(today, /visibleRecordIds = useMemo\(\(\) => \[\.\.\.alerts\.map\(alert => alert\.id\), \.\.\.priority\.map\(signal => signal\.id\)\]/)
})

test('shell clears stale list, detail, and passive entity context across surface changes', () => {
  assert.match(app, /const navigate = \(id: Surface\) => \{ if \(id !== surface \|\| \(id === 'accounts' && detail\)\) \{ clearSelectedEvent\(\); clearMapSelection\(\); clearSelectedAction\(\); clearViewContext\(\); setDetail\(undefined\) \}; setSurface\(id\) \}/)
  assert.match(app, /clearViewContext\(\); setDetail\(await api\.account\(id\)\); setSurface\('accounts'\)/)
  assert.match(app, /active_filters: omniSurface === 'ACCOUNT_DETAIL' \|\| omniSurface === 'MAP' \? undefined : viewContext\.active_filters/)
  assert.match(app, /visible_record_ids: omniSurface === 'ACCOUNT_DETAIL' \|\| omniSurface === 'MAP' \? undefined : viewContext\.visible_record_ids/)
})

test('curated public evidence is never labeled as synthetic demo', () => {
  assert.match(today, /CURATED PUBLIC/)
  assert.match(map, /PUBLIC/)
})

test('Monitor keeps inactive collection separate from curated public preview signals', () => {
  assert.match(monitor, /INACTIVE/)
  assert.match(monitor, /Curated POC signal preview/)
  assert.match(monitor, /CURATED PUBLIC · NOT LIVE INGESTION/)
  assert.match(monitor, /no scheduler or live collector is running/)
  assert.match(monitor, /Open Account 360/)
  assert.match(monitor, /Source freshness/)
  assert.match(monitor, /Last successful check/)
  assert.match(monitor, /No resolved, evidence-backed live events are seller-visible/)
})
