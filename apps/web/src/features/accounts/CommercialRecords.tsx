import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { CanonicalRecord } from '../../components/CanonicalRecord'
import { LoadingStatus } from '../../components/UI'

const collections = ['reference', 'source_package', 'programs', 'components', 'supply_relationships', 'contacts', 'role_targets', 'rfqs', 'quotes', 'quote_revisions', 'quote_lines', 'agreements', 'orders', 'order_lines', 'cancellations', 'shipments', 'acceptances', 'revenue_events', 'invoices', 'payments', 'service_events', 'interactions', 'opportunities', 'actions', 'fulfillment_plans', 'monthly_commercial_history']
const name = (key: string) => key === 'reference' ? 'Account, market, NAICS, site references and commercial requirements' : key === 'source_package' ? 'Imported source package, dates and version' : key.replaceAll('_', ' ')

/** Lazy, paginated disclosure of every retained enriched field in its existing owner. */
export function CommercialRecords({ accountId }: { accountId: string }) {
  const [open, setOpen] = useState(false)
  const [collection, setCollection] = useState('reference')
  const [offset, setOffset] = useState(0)
  const [retry, setRetry] = useState(0)
  const key = `${accountId}:${collection}:${offset}`
  const [loaded, setLoaded] = useState<{ key: string; data: Awaited<ReturnType<typeof api.commercialRecords>> }>()
  const [failure, setFailure] = useState<string>()
  const data = loaded?.key === key ? loaded.data : undefined
  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    void api.commercialRecords(accountId, collection, offset, controller.signal).then(data => {
      if (!controller.signal.aborted) { setLoaded({ key, data }); setFailure(undefined) }
    }).catch(() => { if (!controller.signal.aborted) setFailure(key) })
    return () => controller.abort()
  }, [accountId, collection, offset, key, open, retry])
  return <details className="commercial-records" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Full commercial records &amp; retained input fields</summary>
    {open && <><p>Inspect the canonical source fields, original identity references, assumptions and provenance. Reference-only sites are not verified map locations. Amounts labeled “minor” are integer currency minor units (USD cents); null means unknown.</p>
      <label htmlFor={`commercial-collection-${accountId}`}>Record group</label>
      <select id={`commercial-collection-${accountId}`} value={collection} onChange={event => { setCollection(event.target.value); setOffset(0) }}>{collections.map(value => <option key={value} value={value}>{name(value)}</option>)}</select>
      {failure === key && <p role="alert">This group could not be refreshed. <button type="button" onClick={() => setRetry(value => value + 1)}>Retry record group</button></p>}
      {data ? <div className="commercial-evidence-detail"><small>Canonical revision {data.revision}{data.as_of ? ` · as-of ${data.as_of}` : ''}</small>
        {data.reference ? Object.entries(data.reference).map(([field, value]) => <details key={field}><summary>{name(field)}</summary><CanonicalRecord value={value} /></details>) : <><p>{data.total ?? 0} records · showing {data.records?.length ? offset + 1 : 0}–{offset + (data.records?.length ?? 0)}</p>
          {data.records?.map((record, index) => <details key={String(record[data.record_key ?? ''] ?? offset + index)}><summary>{String(record[data.record_key ?? ''] ?? `Record ${offset + index + 1}`)}</summary><CanonicalRecord value={record} /></details>)}
          <div className="decision-evidence-buttons"><button type="button" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 10))}>Previous records</button><button type="button" disabled={data.next_offset == null} onClick={() => setOffset(data.next_offset!)}>Next records</button></div></>}
      </div> : failure !== key && <LoadingStatus>Opening this commercial record group…</LoadingStatus>}
    </>}
  </details>
}
