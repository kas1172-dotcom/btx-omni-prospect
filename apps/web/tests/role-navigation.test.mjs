import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/app/destinations.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { NAVIGATION_DESTINATIONS, authorizedDestinations, canOpenDestination } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('one exhaustive destination contract owns desktop and mobile discovery', () => {
  assert.equal(new Set(NAVIGATION_DESTINATIONS.map(item => item.surface)).size, NAVIGATION_DESTINATIONS.length)
  for (const destination of NAVIGATION_DESTINATIONS) {
    assert.equal(destination.route, `#/${destination.surface}`)
    assert.ok(destination.label && destination.job && destination.requiredCapability)
    assert.ok(['primary', 'secondary'].includes(destination.desktop))
    assert.ok(['primary', 'secondary'].includes(destination.mobile))
  }
})

test('seller and administrator permissions filter the same destination contract', () => {
  const seller = authorizedDestinations({ authenticated: true, sourceHealth: false })
  const administrator = authorizedDestinations({ authenticated: true, sourceHealth: true })
  const restricted = authorizedDestinations({ authenticated: false, sourceHealth: false })
  assert.ok(seller.some(item => item.surface === 'intelligence'))
  assert.ok(!seller.some(item => item.surface === 'monitor'))
  assert.ok(administrator.some(item => item.surface === 'monitor' && item.label === 'Source Health'))
  assert.deepEqual(restricted, [])
  assert.equal(canOpenDestination('monitor', { authenticated: true, sourceHealth: false }), false)
  assert.equal(canOpenDestination('monitor', { authenticated: true, sourceHealth: true }), true)
})

test('every authorized destination is discoverable at both viewport classes', () => {
  for (const destination of authorizedDestinations({ authenticated: true, sourceHealth: true })) {
    assert.ok(destination.desktop)
    assert.ok(destination.mobile)
  }
})
