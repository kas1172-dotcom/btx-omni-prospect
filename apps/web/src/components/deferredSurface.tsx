import { useEffect, useState, type ComponentType } from 'react'

/** Module-level factory: component identity survives ordinary parent renders.
 * Only code is cached, never user data. A failed import is evicted for retry.
 */
export function deferredSurface<P extends object>(load: () => Promise<ComponentType<P>>, label: string, exportName: string) {
  let loaded: ComponentType<P> | undefined
  let pending: Promise<ComponentType<P>> | undefined
  let retryUrl: URL | undefined
  let retryCount = 0
  const resolve = () => {
    if (pending) return pending
    // Browsers cache failed module-map entries. Retry only this known same-origin
    // workspace module with a bounded cache-busting query, never arbitrary URLs.
    const next = retryUrl && retryCount < 2 ? (() => {
      const url = new URL(retryUrl)
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
      <button className="button" onClick={() => { setFailed(false); setAttempt(value => value + 1) }}>Retry {label} download</button>
    </section>
    return <section className="surface" role="status">Loading {label} workspace… Navigation and Omni remain available.</section>
  }
}
