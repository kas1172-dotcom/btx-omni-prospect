import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/features/map/mapListModel.ts', import.meta.url), 'utf8').then(value => value.replace("import type { MapMarker } from './mapModel'", ''))
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { synchronizedMapSites, synchronizedSiteCount } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('map and list consume the same canonical site array and count', () => {
  const sites = [{ id: 'a', kind: 'customer' }, { id: 'b', kind: 'btx-facility' }]
  assert.strictEqual(synchronizedMapSites(sites), sites)
  assert.equal(synchronizedSiteCount(sites), sites.length)
})

test('presentation clusters never become duplicate list rows', () => {
  const sites = [{ id: 'a', kind: 'customer' }, { id: 'cluster:a|b', kind: 'cluster' }, { id: 'b', kind: 'prospect' }]
  assert.deepEqual(synchronizedMapSites(sites).map(item => item.id), ['a', 'b'])
  assert.equal(synchronizedSiteCount(sites), 2)
})
