import { useEffect, useState, type ComponentType } from 'react'
import { frontendBuild } from '../app/build'
import { LoadingStatus } from './UI'

/** Module-level factory: component identity survives ordinary parent renders.
 * Only code is cached, never user data. A failed import is evicted for retry.
 */
export function deferredSurface<P extends object>(load: () => Promise<ComponentType<P>>, label: string, exportName: string) {
  let loaded: ComponentType<P> | undefined
  let pending: Promise<ComponentType<P>> | undefined
  let retryUrl: URL | undefined
  let retryCount = 0
  let retryRequested = false
  const resolve = () => {
    if (pending) return pending
    // Browsers cache failed module-map entries. Retry only this known same-origin
    // workspace module with a bounded cache-busting query, never arbitrary URLs.
    const next = retryRequested && retryCount < 2 ? (async () => {
      let url = retryUrl && new URL(retryUrl)
      if (!url && import.meta.env.DEV) url = new URL(`/src/features/${exportName.toLowerCase()}/${exportName}.tsx`, window.location.origin)
      if (!url) {
        const response = await fetch('/workspace-modules.json', { cache: 'no-store', signal: AbortSignal.timeout(5000) })
        if (!response.ok) throw new Error('Workspace recovery manifest unavailable')
        const manifest = await response.json()
        if (manifest.build?.built_at !== frontendBuild.built_at || manifest.build?.commit_sha !== frontendBuild.commit_sha) throw new Error('A newer app version is available; reload to recover this workspace')
        const path = manifest.modules?.[exportName]
        if (typeof path !== 'string' || !path.startsWith(`/assets/${exportName}-`) || !/^\/assets\/[\w.-]+\.js$/.test(path)) throw new Error('Invalid workspace recovery module')
        url = new URL(path, window.location.origin)
      }
      // Vite's development HMR normalizes away its timestamp; use the canonical
      // retry URL directly to avoid a second module request/registration.
      if (import.meta.env.DEV) url.searchParams.delete('t')
      url.searchParams.set('btxModuleRetry', String(++retryCount))
      return import(/* @vite-ignore */ url.href).then(module => {
        const component = module[exportName]
        if (typeof component !== 'function') throw new Error('Workspace module export unavailable')
        return component as ComponentType<P>
      })
    })() : load()
    pending = next.then(component => { loaded = component; return component }).catch(error => {
      pending = undefined
      const match = error instanceof Error ? error.message.match(/https?:\/\/[^\s"'<>]+/) : null
      if (match) {
        const url = new URL(match[0])
        const file = url.pathname.split('/').at(-1) ?? ''
        if (url.origin === window.location.origin && !url.username && !url.password
          && ((url.pathname === `/src/features/${exportName.toLowerCase()}/${exportName}.tsx`)
            || (url.pathname.startsWith('/assets/') && file.startsWith(`${exportName}-`) && /^[\w.-]+\.js$/.test(file)))) retryUrl = url
      }
      throw error
    })
    return pending
  }
  return function DeferredSurface(props: P) {
    const [component, setComponent] = useState<ComponentType<P> | undefined>(() => loaded)
    const [attempt, setAttempt] = useState(0)
    const [failed, setFailed] = useState(false)
    useEffect(() => {
      if (component) return
      let active = true
      void resolve().then(value => { if (active) setComponent(() => value) }).catch(() => { if (active) setFailed(true) })
      return () => { active = false }
    }, [component, attempt])
    if (component) {
      const Surface = component
      return <Surface {...props} />
    }
    if (failed) return <section className="surface" aria-label={`${label} loading problem`}>
      <p role="alert">{label} could not be downloaded. Your workspace selection is retained; other sections remain available.</p>
      {retryCount < 2 ? <button className="button" onClick={() => { retryRequested = true; setFailed(false); setAttempt(value => value + 1) }}>Retry {label} download</button>
        : <p>Download recovery is still unavailable. Other workspaces remain usable. Save your drafts before reloading the app.</p>}
    </section>
    return <section className="surface"><LoadingStatus>Preparing {label}… Navigation and Omni remain available.</LoadingStatus></section>
  }
}
