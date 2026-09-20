import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { CanonicalRecord } from '../../components/CanonicalRecord'
import { LoadingStatus } from '../../components/UI'

export function CommercialEvidence({ accountId, recordId }: { accountId: string; recordId: string }) {
  const key = `${accountId}:${recordId}`
  const [loaded, setLoaded] = useState<{ key: string; result: Awaited<ReturnType<typeof api.commercialEvidence>> }>()
  const result = loaded?.key === key ? loaded.result : undefined
  const [errorKey, setErrorKey] = useState<string>()
  const error = errorKey === key
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void api.commercialEvidence(accountId, recordId, controller.signal).then(value => { if (!controller.signal.aborted) { setLoaded({ key, result: value }); setErrorKey(undefined) } }).catch(() => { if (!controller.signal.aborted) setErrorKey(key) })
    return () => controller.abort()
  }, [accountId, recordId, retry, key])
  return <div className="commercial-evidence-detail">{error ? <p role="alert">This record could not be retrieved in the selected account scope. <button onClick={() => setRetry(n => n + 1)}>Retry evidence</button></p> : result ? <><p>{result.kind.replaceAll('_', ' ')} · {result.truth_class.replaceAll('_', ' ').toLowerCase()} · commercial as-of {result.as_of}</p><CanonicalRecord value={result.record} /><small>Canonical revision {result.revision}</small></> : <LoadingStatus>Opening commercial evidence…</LoadingStatus>}</div>
}
