import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/app/navigation.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { workspaceLocation, workspaceHash } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('workspace locations round-trip canonical account and surface identity', () => {
  for (const surface of ['today', 'accounts', 'map', 'actions', 'communications', 'settings', 'monitor', 'intelligence']) {
    assert.deepEqual(workspaceLocation(workspaceHash(surface)), { surface })
  }
  assert.deepEqual(workspaceLocation(workspaceHash('accounts', 'lockheed-martin')), { surface: 'accounts', accountId: 'lockheed-martin' })
})

test('malformed, extra-segment, and traversal account links cannot generate account IDs', () => {
  for (const hash of ['#/accounts/%ZZ', '#/accounts/%2e%2e', '#/accounts/a%2fb', '#/accounts/a/b', '#/accounts/', '#/accounts/' + 'a'.repeat(65)]) {
    assert.deepEqual(workspaceLocation(hash), { surface: 'accounts' })
  }
  assert.deepEqual(workspaceLocation('#/not-a-surface'), { surface: 'today' })
})
