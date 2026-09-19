import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { WorkspaceLocation } from '../../app/navigation'
import { workspaceHash } from '../../app/navigation'
import type { OmniContext } from '../../types/api'
import type { Opportunity } from '../../types/opportunities'
import { ScoreSummary } from '../../components/ScoreSummary'
import { commercialDecisionSummary } from '../../components/scoreSummaryModel'
import { presentationLabel } from '../../components/presentation'
import { CommercialEvidence } from '../accounts/CommercialEvidence'
import { LoadingStatus } from '../../components/UI'
import './opportunities.css'

export function Opportunities({ location, onLocationChange, onOmniContext }: { onOmniContext: (context: Pick<OmniContext, 'selected_account_id' | 'selected_commercial_opportunity'>) => void; location: WorkspaceLocation; onLocationChange: (next: WorkspaceLocation, mode?: 'push' | 'replace') => void }) {
  const [rows, setRows] = useState<Opportunity[]>([])
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    api.opportunities(controller.signal).then(result => { if (!controller.signal.aborted) { setRows(result.opportunities); setState('ready') } }).catch(() => { if (!controller.signal.aborted) setState('error') })
    return () => controller.abort()
  }, [retry])
  const lane = location.filters?.lane === 'PROSPECT' ? 'PROSPECT' : 'CUSTOMER_EXPANSION'
  const query = String(location.filters?.query ?? '')
  const filtered = rows.filter(row => (!location.filters?.account || row.account_id === location.filters.account) && row.lane === lane && `${row.account_name} ${row.title}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => a.account_name.localeCompare(b.account_name) || a.title.localeCompare(b.title) || a.opportunity_id.localeCompare(b.opportunity_id))
  const selected = filtered.find(row => row.opportunity_id === location.recordId)
  useEffect(() => { onOmniContext(selected ? { selected_account_id: selected.account_id, selected_commercial_opportunity: { account_id: selected.account_id, opportunity_id: selected.opportunity_id, revision: selected.revision } } : {}); return () => onOmniContext({}) }, [onOmniContext, selected])
  const change = (filters: Record<string, string>) => onLocationChange({ ...location, recordId: undefined, filters: { ...location.filters, ...filters } })
  return <main className="surface opportunity-workspace"><header><span className="eyebrow">Potential business</span><h1>Opportunities</h1><p>Review a specific requirement separately from the health of the customer relationship.</p></header>
    <div role="tablist" aria-label="Opportunity type">{([['CUSTOMER_EXPANSION', 'Customer expansion'], ['PROSPECT', 'Prospect opportunities']] as const).map(([value, label]) => <button key={value} role="tab" tabIndex={lane === value ? 0 : -1} aria-selected={lane === value} aria-controls="opportunity-results" onKeyDown={event => { if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); const next = event.key === 'Home' ? 'CUSTOMER_EXPANSION' : event.key === 'End' ? 'PROSPECT' : lane === 'PROSPECT' ? 'CUSTOMER_EXPANSION' : 'PROSPECT'; change({ lane: next }); const tabs = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role=tab]'); tabs?.[next === 'PROSPECT' ? 1 : 0]?.focus() } }} onClick={() => change({ lane: value })}>{label}</button>)}</div>
    <label>Search opportunities<input type="search" value={query} onChange={event => change({ query: event.target.value })} /></label>
    {location.filters?.account && <p>Showing one organization. <button onClick={() => { const filters = { ...location.filters }; delete filters.account; onLocationChange({ ...location, recordId: undefined, filters }) }}>Show all organizations</button></p>}
    {state === 'loading' && <LoadingStatus>Preparing opportunities…</LoadingStatus>}
    {state === 'error' && <p role="alert">Opportunities could not be refreshed. <button onClick={() => setRetry(value => value + 1)}>Retry</button></p>}
    <section id="opportunity-results" aria-label={lane === 'PROSPECT' ? 'Prospect opportunities' : 'Customer expansion opportunities'}>
      <p>{filtered.length} recorded {filtered.length === 1 ? 'opportunity' : 'opportunities'}</p>
      {state === 'ready' && !filtered.length && <p>{query ? 'No opportunities match this search.' : 'No scoped opportunities are recorded in this category. An organization or public announcement alone does not establish an opportunity.'}</p>}
      {filtered.length > 0 && <div className="opportunity-table-scroll"><table><thead><tr><th>Opportunity</th><th>Organization</th><th>Stage</th><th>Quoted value</th><th>Attractiveness</th></tr></thead><tbody>{filtered.map(row => <tr key={row.opportunity_id}><th scope="row"><button onClick={() => onLocationChange({ ...location, recordId: row.opportunity_id })} aria-expanded={selected?.opportunity_id === row.opportunity_id}>{row.title}</button></th><td><a href={workspaceHash({ surface: 'accounts', accountId: row.account_id, returnTo: location })}>{row.account_name}</a></td><td>{presentationLabel(row.stage, 'assessment')}</td><td>{new Intl.NumberFormat('en-US', { style: 'currency', currency: row.currency }).format(row.value_minor / 100)}</td><td>{row.attractiveness.score ?? 'Needs opportunity evidence'}</td></tr>)}</tbody></table></div>}
    </section>
    {selected && <section className="opportunity-detail" aria-label="Selected opportunity"><header><h2>{selected.title}</h2><p>{selected.account_name} · {lane === 'CUSTOMER_EXPANSION' ? 'Customer expansion' : 'Prospecting opportunity'}</p><button onClick={() => onLocationChange({ ...location, recordId: undefined })}>Close opportunity</button></header>
      <p>{selected.business_context ?? 'A scoped quote is recorded. Review the source pursuit to establish the commercial case.'}</p>
      {selected.material_uncertainties.map(uncertainty => <p key={uncertainty}><strong>Still unconfirmed:</strong> {uncertainty}</p>)}
      <p><strong>Next step:</strong> {selected.next_action ?? 'No opportunity-specific action is recorded. Review the source pursuit before deciding the next step.'}</p>
      <button onClick={() => window.dispatchEvent(new Event('btx:open-omni'))}>Ask Omni about this opportunity</button>
      <p>Qualification: {selected.qualification_status === 'YES' ? 'Established' : selected.qualification_status === 'NO' ? 'Requirements not met' : 'Needs validation'} · Recurring program: {selected.durability_status === 'YES' ? 'Supported' : selected.durability_status === 'NO' ? 'Not established as recurring' : 'Needs evidence'}</p>
      <ScoreSummary model={{ family: 'Attractiveness', subject: selected.title, decision: 'Evaluate the potential business, not the customer relationship', value: selected.attractiveness.score, interpretation: 'Calculated from this opportunity’s program, manufacturing fit and commercial evidence.', version: selected.attractiveness.configuration_version, coverage: { ratio: selected.attractiveness.coverage }, missingInputs: selected.attractiveness.missingness }} />
      {selected.opportunity_priority.score != null && <ScoreSummary model={commercialDecisionSummary(selected.opportunity_priority, selected.title, 'Compare this opportunity with other potential business')} />}
      {[selected.pwin, selected.delivery_feasibility].filter(decision => decision.status !== 'INELIGIBLE').map(decision => <ScoreSummary key={decision.family} model={commercialDecisionSummary(decision, selected.title)} />)}
      <details><summary>View supporting evidence and qualification gaps</summary><p>Assessment date: {selected.as_of}</p>{[selected.pwin, selected.delivery_feasibility].filter(decision => decision.status === 'INELIGIBLE').map(decision => <section key={decision.family}><h3>{presentationLabel(decision.family)}</h3><ul>{decision.eligibility_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></section>)}<CommercialEvidence key={selected.opportunity_id} accountId={selected.account_id} recordId={selected.source_record_id} /></details>
      <a href={workspaceHash({ surface: 'accounts', accountId: selected.account_id, subview: 'relationships', returnTo: location })}>Explore organization connections</a>
    </section>}
  </main>
}
