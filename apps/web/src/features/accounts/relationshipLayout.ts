import type { CanonicalGraphEdge, CanonicalGraphNode, RankedRelationships as Result, RankedRoute } from '../../types/relationships'
export type Point = { x: number; y: number }
const stableNumber = (value: string) => [...value].reduce((total, character) => ((total * 31) + character.charCodeAt(0)) >>> 0, 2166136261)

export function graphDepths(nodes: CanonicalGraphNode[], edges: CanonicalGraphEdge[], selected?: RankedRoute) {
  const depths = new Map<string, number>()
  selected?.node_ids.forEach((id, index) => depths.set(id, index))
  const origin = selected?.node_ids[0] ?? nodes[0]?.id
  if (!origin) return depths
  depths.set(origin, 0)
  const adjacency = new Map<string, string[]>()
  edges.forEach(edge => { adjacency.set(edge.source, [...(adjacency.get(edge.source) ?? []), edge.target]); adjacency.set(edge.target, [...(adjacency.get(edge.target) ?? []), edge.source]) })
  const queue = [origin]
  while (queue.length) {
    const current = queue.shift() as string
    const nextDepth = (depths.get(current) ?? 0) + 1
    for (const adjacent of adjacency.get(current) ?? []) if (!depths.has(adjacent)) { depths.set(adjacent, nextDepth); queue.push(adjacent) }
  }
  return depths
}

export function initialGraphPositions(result: Result, selected: RankedRoute | undefined, mobile: boolean, previous: Map<string, Point>) {
  const positions = new Map(previous)
  const depths = graphDepths(result.graph.nodes, result.graph.edges, selected)
  if (mobile) {
    selected?.node_ids.forEach((id, index) => { if (!positions.has(id)) positions.set(id, { x: 155, y: 95 + index * 172 }) })
    result.graph.nodes.filter(node => !positions.has(node.id)).toSorted((a, b) => a.id.localeCompare(b.id)).forEach((node, index) => positions.set(node.id, { x: 155, y: 95 + ((selected?.node_ids.length ?? 0) + index) * 172 }))
    return positions
  }
  const center = { x: 150, y: 130 }
  selected?.node_ids.forEach((id, index) => {
    if (positions.has(id)) return
    if (index === 0) { positions.set(id, center); return }
    // A folded ordered route fits beside the inspector without shrinking long
    // paths into unreadable labels. Shared nodes retain their stored positions.
    const row = Math.floor(index / 2)
    const column = row % 2 === 0 ? index % 2 : 1 - index % 2
    positions.set(id, { x: center.x + column * 260, y: center.y + row * 210 })
  })
  const contextByDepth = new Map<number, CanonicalGraphNode[]>()
  result.graph.nodes.filter(node => !positions.has(node.id)).forEach(node => { const depth = Math.min(6, Math.max(1, depths.get(node.id) ?? 2)); contextByDepth.set(depth, [...(contextByDepth.get(depth) ?? []), node]) })
  contextByDepth.forEach((nodesAtDepth, depth) => nodesAtDepth.toSorted((a, b) => a.id.localeCompare(b.id)).forEach((node, index) => {
    const radius = depth * 230
    let angle = -1.28 + (2.56 * (index + 1) / (nodesAtDepth.length + 1)) + ((stableNumber(node.id) % 12) / 100)
    let point = { x: Math.max(110, center.x + Math.cos(angle) * radius), y: Math.max(90, center.y + Math.sin(angle) * radius) }
    for (let attempts = 0; attempts < 16 && [...positions.values()].some(other => Math.abs(other.x - point.x) < 210 && Math.abs(other.y - point.y) < 160); attempts++) { angle += .17; point = { x: Math.max(110, center.x + Math.cos(angle) * radius), y: Math.max(90, center.y + Math.sin(angle) * radius) } }
    while ([...positions.values()].some(other => Math.abs(other.x - point.x) < 210 && Math.abs(other.y - point.y) < 160)) point = { ...point, y: point.y + 170 }
    positions.set(node.id, point)
  }))
  return positions
}
