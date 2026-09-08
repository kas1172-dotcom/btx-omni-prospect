import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { CommercialDecision, FollowupPreview } from '../../types/decisions'
import { CommercialEvidence } from './CommercialEvidence'

const words = (value: string) => value.replaceAll('_', ' ').toLowerCase()
const index = (value: string | number | null) => value == null ? null : new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(Number(value))

function Decision({ decision, onEvidence }: { decision: CommercialDecision; onEvidence: (id: string) => void }) {
  return <details className="commercial-decision"><summary>{words(decision.family)} · {index(decision.score) ?? words(decision.status)}</summary>
    <p>{decision.interpretation}</p><p>Decision coverage: {decision.data_coverage.present}/{decision.data_coverage.applicable} required fields · as-of {decision.as_of}</p>
    {decision.eligibility_reasons.map(reason => <p key={reason}>{reason}</p>)}
    {decision.blocking_constraints.map(reason => <p key={reason}>{reason}</p>)}
    <ul>{decision.factors.map(factor => <li key={factor.key}><strong>{words(factor.key)} · {index(factor.points) ?? 'Not scored'}</strong><p>{factor.reason}</p>
      <details><summary>Evidence and required fields</summary><p>{factor.observed_fields.length}/{factor.required_fields.length} fields present. Required: {factor.required_fields.map(words).join(', ')}.</p>
        <div className="decision-evidence-buttons">{factor.evidence_ids.map(id => <button key={id} type="button" onClick={() => onEvidence(id)}>{id}</button>)}</div></details></li>)}</ul>
    <small>Provisional configuration {decision.configuration_version}. {decision.decision_id}</small>
  </details>
}

function Followup({ accountId, actionId, onCreated }: { accountId: string; actionId: string; onCreated: () => void }) {
  const [preview, setPreview] = useState<FollowupPreview>()
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState('')
  const inspect = async () => {
    setPending(true); setNotice('')
    try { setPreview(await api.followupPreview(accountId, actionId)) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Preview unavailable. Try again.') }
    finally { setPending(false) }
  }
  const confirm = async () => {
    if (!preview || pending) return
    setPending(true); setNotice('')
    try {
      const action = await api.confirmFollowup(accountId, actionId, preview.preview_token)
      setNotice(`Local work ${action.id} is ${words(action.status)}. No external system was changed.`)
      setPreview(undefined); onCreated()
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Creation was not confirmed. Retry with the same preview or refresh it.') }
    finally { setPending(false) }
  }
  return <div><button type="button" disabled={pending} onClick={() => void inspect()}>{pending ? 'Working…' : 'Preview local follow-up'}</button>
    {preview && <section aria-label="Local follow-up preview"><h4>{preview.destination}</h4><p><strong>{preview.proposal.title}</strong></p><p>{preview.proposal.description}</p>
      <dl><dt>Owner</dt><dd>{preview.proposal.owner_id}</dd><dt>Due</dt><dd>{preview.proposal.due_date ?? 'Not set'}</dd><dt>Priority</dt><dd>{words(preview.proposal.priority)}</dd></dl>
      <p>{preview.note}</p><p>Supporting records: {preview.proposal.evidence_ids.join(', ')}</p>
      {preview.existing_work_id ? <p>Already linked: {preview.existing_work_id} · {words(preview.existing_work_status ?? '')}. Review it in Work; no duplicate will be created.</p> : <button type="button" disabled={pending} onClick={() => void confirm()}>Confirm local follow-up</button>}
      <button type="button" disabled={pending} onClick={() => setPreview(undefined)}>Close preview</button></section>}
    {notice && <p role="status">{notice}</p>}</div>
}

export function CommercialDecisions({ accountId, onWorkChanged }: { accountId: string; onWorkChanged: () => void }) {
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.commercialDecisions>>>()
  const [error, setError] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const [evidence, setEvidence] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    void api.commercialDecisions(accountId, controller.signal).then(value => { if (!controller.signal.aborted) { setResult(value); setError(false) } }).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [accountId, refresh])
  return <div className="commercial-decisions"><p>Separate decisions answer different questions. Missing qualification, capacity and buyer evidence cannot be replaced by a high relationship index.</p>
    {error && <p role="alert">Decisions could not be refreshed. Displayed results may be outdated. <button onClick={() => setRefresh(n => n + 1)}>Retry decisions</button></p>}
    {result ? <><Decision decision={result.customer_health} onEvidence={setEvidence} /><Decision decision={result.internal_commercial_risk} onEvidence={setEvidence} />
      {result.opportunities.map(opportunity => <section key={opportunity.opportunity_id}><h3>{opportunity.opportunity_id} · {opportunity.component_id}</h3><p>{words(opportunity.stage)} · {new Intl.NumberFormat('en-US', { style: 'currency', currency: opportunity.currency }).format(opportunity.value_minor / 100)} quoted opportunity</p>
        <p>{words(opportunity.qualification_status)} · {words(opportunity.durability_status)}</p>
        {[opportunity.opportunity_priority, opportunity.pwin, opportunity.delivery_feasibility].map(decision => <Decision key={decision.family} decision={decision} onEvidence={setEvidence} />)}</section>)}
      {result.action_priorities.map(action => <section key={action.action_id}><h3>{action.title}</h3><p>{words(action.work_status)}</p><Decision decision={action.decision} onEvidence={setEvidence} />
        <Followup accountId={accountId} actionId={action.action_id} onCreated={() => { setRefresh(n => n + 1); onWorkChanged() }} /></section>)}</> : !error && <p role="status">Loading canonical decisions…</p>}
    {evidence && <section aria-label="Decision supporting evidence"><h3>Supporting record {evidence}</h3><button onClick={() => setEvidence('')}>Close supporting record</button><CommercialEvidence key={`${accountId}:${evidence}`} accountId={accountId} recordId={evidence} /></section>}
  </div>
}
