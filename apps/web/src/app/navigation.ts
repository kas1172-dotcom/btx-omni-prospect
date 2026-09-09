export type Surface = 'today' | 'accounts' | 'intelligence' | 'map' | 'actions' | 'communications' | 'settings' | 'monitor'
const surfaces = new Set<Surface>(['today', 'accounts', 'intelligence', 'map', 'actions', 'communications', 'settings', 'monitor'])

export function workspaceLocation(hash: string): { surface: Surface; accountId?: string } {
  const parts = hash.replace(/^#\/?/, '').split('/')
  const surface = surfaces.has(parts[0] as Surface) ? parts[0] as Surface : 'today'
  if (surface === 'accounts' && parts.length === 2) {
    try {
      const id = decodeURIComponent(parts[1])
      if (/^[a-zA-Z0-9_-]{1,64}$/.test(id)) return { surface, accountId: id }
    } catch { /* Malformed deep links cannot become API paths. */ }
  }
  return { surface }
}

export function workspaceHash(surface: Surface, accountId?: string): string {
  return `#/${surface}${surface === 'accounts' && accountId ? `/${encodeURIComponent(accountId)}` : ''}`
}
