import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/features/map/mapViewport.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
const { computeViewport, DEFAULT_US_VIEW } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const point = (latitude, longitude) => ({ latitude, longitude })

test('zero points keeps current view or uses the default US view', () => {
  assert.deepEqual(computeViewport({ points: [] }), { kind: 'keep', ...DEFAULT_US_VIEW })
  assert.deepEqual(computeViewport({ points: [], current: { center: point(40, -90), zoom: 7 } }), { kind: 'keep', center: point(40, -90), zoom: 7 })
})

test('one point, duplicates, and clusters under two kilometers use fixed site zoom', () => {
  assert.deepEqual(computeViewport({ points: [point(39, -90)] }), { kind: 'center', center: point(39, -90), zoom: 12 })
  assert.equal(computeViewport({ points: [point(39, -90), point(39, -90)] }).kind, 'center')
  assert.equal(computeViewport({ points: [point(39, -90), point(39.01, -90.01)] }).kind, 'center')
})

test('US-wide spread returns capped bounds with overlay-aware padding', () => {
  const result = computeViewport({ points: [point(34, -118), point(41, -72)], padding: { right: 380 } })
  assert.equal(result.kind, 'bounds')
  assert.equal(result.maxZoom, 13)
  assert.equal(result.padding.right, 380)
  assert.deepEqual(result.bounds, { north: 41, south: 34, east: -72, west: -118 })
})

test('invalid coordinates are removed before camera planning', () => {
  assert.deepEqual(computeViewport({ points: [point(NaN, 2), point(91, 0), point(38, -98)] }), { kind: 'center', center: point(38, -98), zoom: 12 })
})

test('provider viewport takes precedence and radius fits a circle around the origin', () => {
  const viewport = { north: 42, south: 40, east: -70, west: -74 }
  assert.deepEqual(computeViewport({ viewport, points: [point(0, 0)] }).bounds, viewport)
  const radius = computeViewport({ origin: point(40, -75), radiusMiles: 50 })
  assert.equal(radius.kind, 'bounds')
  assert.ok(radius.bounds.north > 40 && radius.bounds.south < 40)
  assert.ok(radius.bounds.east > -75 && radius.bounds.west < -75)
})

test('camera planning is idempotent for identical explicit intent', () => {
  const request = { points: [point(34, -118), point(41, -72)], padding: { right: 360 } }
  assert.deepEqual(computeViewport(request), computeViewport(structuredClone(request)))
})
