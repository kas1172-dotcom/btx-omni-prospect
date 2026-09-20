import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { RelatedBtxRecord } from '../types/api'
import { CanonicalRecord } from './CanonicalRecord'
import { Button, Empty, LoadingStatus, StatusBadge } from './UI'

const label = (value: string) => value.replaceAll('_', ' ').toLowerCase().replace(/^./, letter => letter.toUpperCase())
const money = (record: RelatedBtxRecord) => {
  const minor = record.total_minor ?? record.line_total_minor ?? record.amount_minor ?? record.value_minor
  return minor == null ? null : new Intl.NumberFormat('en-US', { style: 'currency', currency: record.currency ?? 'USD', maximumFractionDigits: 0 }).format(minor / 100)
}

export function RelatedBtxActivity({ accountId, records, initialRecordId, onRecord }: { accountId: string; records: RelatedBtxRecord[]; initialRecordId?: string; onRecord?: (recordId?: string) => void }) {
  const [detail, setDetail] = useState<{ key: string; loading: boolean; value?: Record<string, unknown>; error?: string }>()
  const inspect = async (record: RelatedBtxRecord) => {
    const key = `${record.collection}:${record.record_id}`
    if (detail?.key === key) { setDetail(undefined); onRecord?.(); return }
    onRecord?.(record.record_id)
    setDetail({ key, loading: true })
    try {
      const result = await api.commercialRecord(accountId, record.collection, record.record_id)
      setDetail({ key, loading: false, value: result.records[0] })
    } catch {
      setDetail({ key, loading: false, error: 'The source record could not be loaded. The assessment context remains selected.' })
    }
  }
  useEffect(() => {
    if (!initialRecordId) return
    if (detail) return
    const record = records.find(item => item.record_id === initialRecordId)
    if (!record) return
    const key = `${record.collection}:${record.record_id}`
    const controller = new AbortController()
    void api.commercialRecord(accountId, record.collection, record.record_id, controller.signal).then(result => { if (!controller.signal.aborted) setDetail({ key, loading: false, value: result.records[0] }) }).catch(() => { if (!controller.signal.aborted) setDetail({ key, loading: false, error: 'The source record could not be loaded. The assessment context remains selected.' }) })
    return () => controller.abort()
  }, [accountId, detail, initialRecordId, records])
  if (!records.length) return <Empty>No related BTX activity was found. This does not establish that no relationship exists.</Empty>
  return <div className="related-activity-list" id="related-btx-activity">{records.map(record => {
    const key = `${record.collection}:${record.record_id}`
    const expanded = detail?.key === key && (!initialRecordId || initialRecordId === record.record_id)
    return <article className="related-activity" key={key}>
      <div><span className="eyebrow">{label(record.collection)}</span><h4>{record.display_name}</h4><p>{record.date || 'Date unavailable'}{record.status ? ` · ${label(record.status)}` : ''}{money(record) ? ` · ${money(record)}` : ''}</p></div>
      <StatusBadge value={record.match_strength} kind="evidence" />
      <p><strong>Why Omni selected it:</strong> {record.match_reasons.join(' · ')}</p>
      <p><strong>Still unknown:</strong> {record.unknowns}</p>
      <p><strong>Validate:</strong> {record.validation_action}</p>
      <Button variant="ghost" aria-expanded={expanded} onClick={() => void inspect(record)}>{expanded ? 'Close source record' : 'Inspect source record'}</Button>
      {expanded && <div className="related-activity-source" role="region" aria-label={`${record.display_name} source record`}>{detail.loading ? <LoadingStatus>Opening the supporting record…</LoadingStatus> : detail.error ? <p role="alert">{detail.error}</p> : detail.value ? <CanonicalRecord value={detail.value} /> : null}</div>}
    </article>
  })}</div>
}
