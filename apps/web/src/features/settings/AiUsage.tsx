import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { Button, Disclosure, LoadingStatus } from '../../components/UI'

export interface AiUsageSummary {
  policy_version: string
  utc_day: string
  workspace_reserved_calls: number
  your_reserved_calls: number
  your_measured_total_tokens: number | null
  your_unknown_usage_calls: number
  limits: { workspace_daily_calls: number; your_daily_calls: number; workspace_concurrent_calls: number; your_concurrent_calls: number }
}

export function AiUsage() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<AiUsageSummary>()
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    api.aiUsage(controller.signal).then(value => {
      if (!controller.signal.aborted) setData(value)
    }).catch(() => {
      if (!controller.signal.aborted) setError('Usage could not be refreshed. Try again; prior values, if shown, are not current.')
    }).finally(() => { if (!controller.signal.aborted) setPending(false) })
    return () => controller.abort()
  }, [open, refresh])
  return <Disclosure className="settings-section" title="AI call budget and usage" onOpenChange={value => { setOpen(value); setPending(value); setError('') }}>
    <p>Daily call limits are provisional workspace controls, not provider billing or a measure of successful answers. Failed and uncertain calls count toward these limits.</p>
    {error && <p role="alert">{error}</p>}
    {pending && <LoadingStatus>Refreshing AI usage…</LoadingStatus>}
    {data && <dl className="action-meta">
      <div><dt>UTC accounting day</dt><dd>{data.utc_day}</dd></div>
      <div><dt>Your reserved calls</dt><dd>{data.your_reserved_calls} / {data.limits.your_daily_calls}</dd></div>
      <div><dt>Workspace reserved calls</dt><dd>{data.workspace_reserved_calls} / {data.limits.workspace_daily_calls}</dd></div>
      <div><dt>Concurrent call leases</dt><dd>{data.limits.your_concurrent_calls} per user; {data.limits.workspace_concurrent_calls} workspace-wide</dd></div>
      <div><dt>Your measured tokens</dt><dd>{data.your_measured_total_tokens?.toLocaleString() ?? 'Not available'}; {data.your_unknown_usage_calls} calls have unknown usage</dd></div>
      <div><dt>Cost</dt><dd>Not measured; consult provider billing</dd></div>
      <div><dt>Policy</dt><dd>{data.policy_version}</dd></div>
    </dl>}
    <Button disabled={pending} onClick={() => { setPending(true); setError(''); setRefresh(value => value + 1) }}>Refresh AI usage</Button>
  </Disclosure>
}
