import { Fragment, useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { Account360 } from '../../types/api'
import { CanonicalRecord } from '../../components/CanonicalRecord'
import { Followup } from './CommercialDecisions'

type Row = Record<string, unknown>
const collections = ['orders', 'order_lines', 'shipments', 'cancellations', 'quotes', 'quote_revisions', 'rfqs', 'agreements', 'service_events', 'actions']
const text = (value: unknown) => value == null ? 'Unknown' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const amount = (value: unknown, currency: string) => typeof value === 'number' ? new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value / 100) : 'Unknown'

export function ProfileCommercial({ detail, onWorkChanged }: { detail: Account360; onWorkChanged: () => void }) {
  const [data, setData] = useState<Record<string, Row[]>>()
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [expanded, setExpanded] = useState<string>()
  const accountId = detail.account.id
  const available = Boolean(detail.commercial_ledger)
  useEffect(() => {
    if (!available) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort('timeout'), 20000)
    const read = async (collection: string) => {
      const rows: Row[] = []; let offset: number | null = 0
      while (offset != null) {
        const page = await api.commercialRecords(accountId, collection, offset, controller.signal)
        rows.push(...(page.records ?? [])); offset = page.next_offset ?? null
      }
      return [collection, rows] as const
    }
    void Promise.all(collections.map(read)).then(entries => { if (!controller.signal.aborted) { setData(Object.fromEntries(entries)); setError('') } }).catch(() => { if (!controller.signal.aborted || controller.signal.reason === 'timeout') setError('Commercial records could not be loaded. No values have been inferred.') }).finally(() => window.clearTimeout(timer))
    return () => { controller.abort(); window.clearTimeout(timer) }
  }, [accountId, available, retry])
  if (!available) return <section className="profile-card"><h2>Commercial</h2><p>No linked commercial ledger. No revenue, orders or quote totals are inferred for this account.</p>{Object.entries(detail.commercial_source_states).map(([name, state]) => <p key={name}>{name}: {state.source_state} · {state.data_mode}</p>)}</section>
  if (!data) return <section className="profile-card" aria-busy={!error}>{error ? <p role="alert">{error} <button onClick={() => { setError(''); setRetry(n => n + 1) }}>Retry commercial records</button></p> : <p role="status">Loading canonical commercial records…</p>}</section>
  const ledger = detail.commercial_ledger!
  const currency = ledger.currency
  const asOf = ledger.as_of
  const lines = detail.profile.fulfillment?.lines ?? []
  const prices = new Map(data.order_lines.map(row => [row.order_line_id, row.unit_price_minor]))
  const openValue = (selected: typeof lines) => selected.every(row => typeof prices.get(row.order_line_id) === 'number') ? selected.reduce((sum, row) => sum + row.remaining_quantity * Number(prices.get(row.order_line_id)), 0) : null
  const decisions: Array<{ kind: string; id: string; recordIds: string[]; value: unknown; date: string }> = lines.filter(row => row.overdue).map(row => ({ kind: 'Late shipment commitment', id: row.order_line_id, recordIds: [row.order_line_id, row.order_id], value: openValue([row]), date: row.committed_date ?? 'Unknown' }))
  for (const quote of data.quotes.filter(row => row.status === 'OPEN')) {
    const revision = data.quote_revisions.find(row => row.quote_revision_id === quote.current_revision_id)
    const ids = [text(quote.quote_id), text(quote.current_revision_id)]
    const decisionDate = quote.decision_due_date ?? quote.decision_date
    if (typeof decisionDate === 'string' && decisionDate < asOf) decisions.push({ kind: 'Quote past decision date', id: text(quote.quote_id), recordIds: ids, value: revision?.total_minor, date: decisionDate })
    if (typeof revision?.valid_until === 'string') {
      const days = (Date.parse(revision.valid_until) - Date.parse(asOf)) / 86400000
      if (days <= 30) decisions.push({ kind: days < 0 ? 'Expired open quote' : 'Quote expires within 30 days', id: text(quote.quote_id), recordIds: ids, value: revision.total_minor, date: revision.valid_until })
    }
  }
  const recordTable = (collection: string, title: string) => {
    const rows = data[collection]
    const keys = [...new Set(rows.flatMap(row => Object.keys(row)))].filter(key => key !== 'provenance' && !rows.some(row => row[key] != null && typeof row[key] === 'object')).slice(0, 8)
    return <section className="profile-card"><h2>{title} <small>({rows.length})</small></h2>{rows.length ? <div className="profile-table-wrap"><table className="profile-table"><thead><tr>{keys.map(key => <th key={key}>{key.replaceAll('_', ' ')}</th>)}<th>Source record</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${collection}:${index}`}>{keys.map(key => <td key={key}>{key.endsWith('_minor') ? amount(row[key], currency) : text(row[key])}</td>)}<td><details><summary>Evidence & fields</summary><CanonicalRecord value={row} /></details></td></tr>)}</tbody></table></div> : <p>No {title.toLowerCase()} in the imported ledger.</p>}</section>
  }
  return <div className="profile-commercial"><aside className="profile-sample-banner"><strong>SAMPLE</strong> Canonical snapshot {asOf} · {currency}. Amounts are not live commitments.</aside>
    <section className="profile-card"><h2>Commercial decision panel</h2><p>Late commitments, open quote expiry (next 30 days), and past decision dates.</p>{decisions.length ? <div className="profile-table-wrap"><table className="profile-table"><thead><tr><th>Attention</th><th>Record</th><th>Dollars</th><th>Date</th><th>Create action</th></tr></thead><tbody>{decisions.map(row => {
      const action = data.actions.find(action => Array.isArray(action.evidence_record_ids) && action.evidence_record_ids.some(id => row.recordIds.includes(String(id))))
      return <tr key={`${row.kind}:${row.id}`}><td>{row.kind}</td><td>{row.id}</td><td>{amount(row.value, currency)}</td><td>{row.date}</td><td>{action ? <Followup accountId={accountId} actionId={text(action.action_id)} onCreated={onWorkChanged} /> : <span>No canonical follow-up linked. Create is unavailable; review in Actions.</span>}</td></tr>
    })}</tbody></table></div> : <p>No matching decision records in this snapshot.</p>}</section>
    <section className="profile-card"><h2>Orders</h2><p>Recorded order history, with shipment and cancellation-aware open quantities. Not automatically the TTM window.</p><div className="profile-table-wrap"><table className="profile-table"><thead><tr>{['Order', 'Ordered', 'Shipped', 'Open', 'Open value', 'Due', 'Status'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{[...data.orders].reverse().map(row => {
      const id = text(row.order_id); const selected = lines.filter(line => line.order_id === id); const rawLines = data.order_lines.filter(line => line.order_id === id)
      const ids = new Set(rawLines.map(line => line.order_line_id))
      return <Fragment key={id}><tr><th scope="row"><button aria-expanded={expanded === id} onClick={() => setExpanded(expanded === id ? undefined : id)}>{id}</button></th><td>{selected.length ? selected.reduce((sum, line) => sum + line.ordered_quantity, 0) : 'Unknown'}</td><td>{selected.length ? selected.reduce((sum, line) => sum + line.shipped_quantity, 0) : 'Unknown'}</td><td>{selected.length ? selected.reduce((sum, line) => sum + line.remaining_quantity, 0) : 'Unknown'}</td><td>{selected.length ? amount(openValue(selected), currency) : 'Unknown'}</td><td>{[...new Set(selected.map(line => line.committed_date ?? 'Unknown'))].join(', ') || 'Unknown'}</td><td>{text(row.status)}</td></tr>{expanded === id && <tr><td colSpan={7}><h3>Lines, shipments & cancellations</h3><CanonicalRecord value={{ order: row, lines: rawLines, fulfillment: selected, shipments: data.shipments.filter(ship => ids.has(ship.order_line_id)), cancellations: data.cancellations.filter(cancel => ids.has(cancel.order_line_id)) }} /></td></tr>}</Fragment>
    })}</tbody></table></div></section>
    {recordTable('quotes', 'Quotes')}{recordTable('rfqs', 'RFQs')}{recordTable('agreements', 'Agreements')}{recordTable('service_events', 'Service events')}
    <details><summary>Commercial source states</summary><CanonicalRecord value={detail.commercial_source_states} /></details>
  </div>
}
