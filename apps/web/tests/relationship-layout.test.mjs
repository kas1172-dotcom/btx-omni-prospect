import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/features/accounts/relationshipLayout.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { initialGraphPositions } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const nodes = Array.from({ length: 7 }, (_, i) => ({ id: `node-${i}` }))
const route = { node_ids: nodes.map(n => n.id) }
const result = { graph: { nodes, edges: [] } }

test('all six actual hops have non-overlapping labels; longer routes do not collapse onto one ring', () => {
  const positions = [...initialGraphPositions(result, route, false, new Map()).values()]
  for (let i = 0; i < positions.length; i++) for (let j = i + 1; j < positions.length; j++) {
    assert.ok(Math.abs(positions[i].x - positions[j].x) >= 210 || Math.abs(positions[i].y - positions[j].y) >= 160)
  }
})
test('expansion preserves every existing canonical position and mobile keeps ordered steps distinct', () => {
  const original = initialGraphPositions(result, route, false, new Map())
  const expanded = initialGraphPositions({ graph: { nodes: [...nodes, { id: 'extra' }], edges: [] } }, route, false, original)
  for (const [key, value] of original) assert.deepEqual(expanded.get(key), value)
  const mobile = [...initialGraphPositions(result, route, true, new Map()).values()]
  assert.equal(new Set(mobile.map(p => p.y)).size, 7)
})
