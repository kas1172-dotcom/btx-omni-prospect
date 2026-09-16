import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/app/navigation.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { decodeWorkspaceLocation, historyUpdate, workspaceLocation, workspaceHash } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('workspace locations round-trip the complete stable investigation context', () => {
  const location = {
    surface: 'accounts', accountId: 'lockheed-martin', scope: 'FACILITY', facilityId: 'troy-al', partnershipId: 'rtx-collins-aerospace', subview: 'relationships',
    assessment: { assessmentId: 'assessment-4', assessmentVersion: 4, eventId: 'event-javelin', accountId: 'lockheed-martin' },
    federal: { opportunityId: 'SAM-1', assessmentId: 'federal-a1', assessmentVersion: 3, routeType: 'STRATEGIC_PARTNER', accountId: 'lockheed-martin', partnershipId: 'rtx-collins-aerospace' },
    relationship: { pathId: 'path-2', mode: 'commercial-fit', startAccountId: 'lockheed-martin' },
    filters: { market: 'Defense', status: ['OPEN', 'IN_PROGRESS'] }, sort: 'priority', anchor: 'assessment-4',
    returnTo: { surface: 'intelligence', subview: 'federal', filters: { notice_type: 'Sources Sought' }, sort: 'relevance', anchor: 'SAM-1' },
  }
  assert.equal(workspaceHash(workspaceLocation(workspaceHash(location))), workspaceHash(location))
  for (const surface of ['today', 'accounts', 'map', 'actions', 'communications', 'settings', 'monitor', 'intelligence']) assert.equal(workspaceLocation(workspaceHash(surface)).surface, surface)
})

test('legacy hashes normalize without losing supported selection', () => {
  assert.equal(decodeWorkspaceLocation('#/intelligence/federal').canonicalHash, '#/intelligence?view=federal')
  assert.equal(decodeWorkspaceLocation('#/intelligence/brief/event-1').canonicalHash, '#/intelligence?view=brief&record=event-1')
  assert.equal(decodeWorkspaceLocation('#/today/brief/recovery-1').canonicalHash, '#/today?view=recovery&record=recovery-1')
  assert.equal(decodeWorkspaceLocation('#/settings/access').canonicalHash, '#/settings?view=access')
  assert.equal(workspaceLocation('#/accounts/lockheed-martin').accountId, 'lockheed-martin')
})

test('malformed and contradictory context is rejected without retaining unsafe identifiers', () => {
  for (const hash of ['#/accounts/%ZZ', '#/accounts/%2e%2e', '#/accounts/a%2fb', '#/accounts/a/b', '#/accounts/' + 'a'.repeat(201), '#/accounts/x?assessment=a&av=4', '#/map?scope=facility', '#/intelligence?view=unknown']) {
    const decoded = decodeWorkspaceLocation(hash)
    assert.equal(decoded.recovery, 'malformed', hash)
    assert.doesNotMatch(decoded.canonicalHash, /%2F|unknown/)
  }
  assert.equal(decodeWorkspaceLocation('#/not-a-surface').location.surface, 'today')
})

test('an event-only selection is valid without inventing assessment context', () => {
  const decoded = decodeWorkspaceLocation('#/map?account_id=lockheed-martin&event=evt-javelin&scope=account')
  assert.equal(decoded.recovery, undefined)
  assert.equal(decoded.location.eventId, 'evt-javelin')
  assert.equal(decoded.location.assessment, undefined)
  assert.equal(decoded.canonicalHash, '#/map?account_id=lockheed-martin&event=evt-javelin&scope=account')
})

test('history decisions avoid render loops while preserving meaningful push and filter replace operations', () => {
  assert.deepEqual(historyUpdate('#/today', { surface: 'today' }, 'push'), { method: 'none', hash: '#/today' })
  assert.equal(historyUpdate('#/today', { surface: 'accounts', accountId: 'boeing' }, 'push').method, 'push')
  assert.equal(historyUpdate('#/actions', { surface: 'actions', filters: { status: 'OPEN' } }, 'replace').method, 'replace')
})
