import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { LoadingStatus } from '../../components/UI'
import './workbook-fields.css'

export interface WorkbookPage {
  total: number; next_offset: number | null; authority: string
  items: Array<{ row_key: string; workbook: string; workbook_sha256: string; sheet: string; row_number: number; version_id: string; source_organization: string; fields: Array<{ column: string; source_cell: string; source_header_cell: string; source_header: string; label: string; group: string; value: string | number | boolean | null; disposition: string; source_formula?: string; validation_state?: string }> }>
}

export function WorkbookFields({ accountId }: { accountId: string }) {
  const [open, setOpen] = useState(false)
  return <details className="workbook-fields" onToggle={event => { if (event.currentTarget.open) setOpen(true) }}><summary>Original workbook fields</summary>{open && <WorkbookPageView key={accountId} accountId={accountId} />}</details>
}

function WorkbookPageView({ accountId }: { accountId: string }) {
  const [offset, setOffset] = useState(0)
  const [retry, setRetry] = useState(0)
  const [loaded, setLoaded] = useState<{ offset: number; data: WorkbookPage }>()
  const [failed, setFailed] = useState<number>()
  const current = loaded?.offset === offset
  useEffect(() => {
    const controller = new AbortController()
    void api.workbookFields(accountId, offset, controller.signal).then(data => {
      if (!controller.signal.aborted) { setLoaded({ offset, data }); setFailed(undefined) }
    }).catch(() => { if (!controller.signal.aborted) setFailed(offset) })
    return () => controller.abort()
  }, [accountId, offset, retry])
  return <div aria-busy={!current && failed !== offset}>
    <p>Private source references, not current transactions, verified locations or official scores. Original units and periods are retained.</p>
    {failed === offset ? <p role="alert">Workbook fields could not be retrieved. <button onClick={() => setRetry(value => value + 1)}>Retry workbook fields</button></p> : !current && <LoadingStatus>Opening retained source rows…</LoadingStatus>}
    {loaded && <div aria-label={current ? 'Current source rows' : 'Previously loaded source rows'}>
      {!current && <p>Previously loaded rows remain visible while this page loads.</p>}
      {loaded.data.total === 0 && <p>No original workbook row is associated with this account.</p>}
      {loaded.data.items.map(row => <details key={row.version_id}>
        <summary>{row.workbook} · {row.sheet} · row {row.row_number}</summary>
        <p>Original organization: {row.source_organization}</p>
        {['company', 'site', 'classification', 'legacy_commercial'].map(group => {
          const fields = row.fields.filter(field => field.group === group)
          return fields.length > 0 && <section key={group}><h4>{group.replaceAll('_', ' ')}</h4><dl>{fields.map(field => <div key={field.column}>
            <dt>{field.label} <small>({field.source_cell})</small></dt>
            <dd>{field.source_formula ? 'Invalid source formula cache — not a usable phone number' : field.value === null ? 'Not supplied' : String(field.value)}
              <details><summary>Field provenance</summary><p>Original header: {field.source_header || '(unlabeled)'} · {field.source_header_cell}</p><p>{field.disposition.replaceAll('_', ' ').toLowerCase()}</p>{field.source_formula && <p>Unevaluated original formula: <code>{field.source_formula}</code> · original cached value: {String(field.value)}</p>}</details>
            </dd>
          </div>)}</dl></section>
        })}
        <details><summary>Source and immutable version</summary><p>Workbook SHA-256: <code>{row.workbook_sha256}</code></p><p>Reference version: <code>{row.version_id}</code></p></details>
      </details>)}
      <p>{loaded.data.total} associated source rows</p>
      <nav aria-label="Workbook field pages"><button disabled={!current || offset === 0} onClick={() => setOffset(value => Math.max(0, value - 3))}>Previous source rows</button><button disabled={!current || loaded.data.next_offset === null} onClick={() => setOffset(loaded.data.next_offset ?? offset)}>Next source rows</button></nav>
    </div>}
  </div>
}
