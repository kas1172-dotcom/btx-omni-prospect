import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { CanonicalRecord } from '../../components/CanonicalRecord'
import { Button } from '../../components/UI'
import type { Action, Principal } from '../../types/api'
import type { CrmAttempt, CrmDecision, CrmHistory, CrmProposal } from '../../types/crm'
import { presentationLabel } from '../../components/presentation'

export function CrmProposalPanel({ action, principal }: { action: Action; principal?: Principal }) {
  const [activated, setActivated] = useState(false)
  return <details className="crm-proposal-panel" onToggle={event => { if (event.currentTarget.open) setActivated(true) }}><summary>CRM proposal and approval workflow</summary>{activated && <CrmWorkflow key={action.id} action={action} principal={principal} />}</details>
}

function CrmWorkflow({ action, principal }: { action: Action; principal?: Principal }) {
  const [history, setHistory] = useState<CrmHistory>()
  const [selectedId, setSelectedId] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reload, setReload] = useState(0)
  const inFlight = useRef(false)
  const epoch = useRef(0)
  const retry = useRef<{ signature: string; key: string } | undefined>(undefined)
  const proposals = history?.events.filter(event => event.kind === 'CRM_PROPOSED').map(event => event.data as CrmProposal) ?? []
  const proposal = proposals.find(item => item.proposal_id === selectedId) ?? proposals.find(item => item.proposal_id === history?.current_proposal_id) ?? proposals.at(-1)
  const decisions = history?.events.filter(event => event.kind === 'CRM_DECIDED' && event.data.proposal_id === proposal?.proposal_id).map(event => event.data as CrmDecision) ?? []
  const decision = decisions.at(-1)
  const attempts = history?.events.filter(event => event.kind === 'CRM_SAMPLE_ATTEMPT' && event.data.proposal_id === proposal?.proposal_id).map(event => event.data as CrmAttempt) ?? []
  const lastAttempt = attempts.at(-1)
  const current = proposal?.proposal_id === history?.current_proposal_id && proposal?.action_version === action.version
  const manager = principal?.role === 'MANAGER'

  useEffect(() => {
    const controller = new AbortController()
    const read = ++epoch.current
    void api.crmHistory(action.id, controller.signal).then(value => {
      if (!controller.signal.aborted && epoch.current === read) { setHistory(value); setError('') }
    }).catch(() => { if (!controller.signal.aborted && epoch.current === read) setError('CRM proposal history could not be loaded. Retry refresh; no operation was confirmed.') })
    return () => controller.abort()
  }, [action.id, action.version, reload])

  const run = async (operation: () => Promise<string>) => {
    if (inFlight.current) return
    inFlight.current = true; ++epoch.current; setBusy(true); setError(''); setNotice('')
    try { setNotice(await operation()); setHistory(await api.crmHistory(action.id)) }
    catch (caught) { setError(`${caught instanceof Error ? caught.message : 'Outcome could not be confirmed.'} Refresh to inspect saved receipts. An uncertain retry retains its request key.`) }
    finally { inFlight.current = false; setBusy(false) }
  }
  const prepare = () => run(async () => {
    const result = await api.crmPreview(action.id, action.version)
    setSelectedId(result.proposal_id)
    return 'Exact proposal saved for review. No CRM operation was executed.'
  })
  const approve = (value: 'APPROVED' | 'REJECTED') => run(async () => {
    if (!proposal) return 'Prepare a proposal first.'
    const result = await api.crmDecision(action.id, { proposal_id: proposal.proposal_id, decision: value, expected_decision_id: decision?.decision_id ?? null })
    return result.is_current === false ? 'Earlier approval receipt recovered; inspect the current decision before proceeding.' : `Proposal ${value.toLowerCase()} by the Manager. No CRM operation was executed.`
  })
  const attempt = () => run(async () => {
    if (!proposal || !decision) return 'An approved proposal is required.'
    const signature = `${proposal.proposal_id}:${decision.decision_id}`
    if (retry.current?.signature !== signature) retry.current = { signature, key: crypto.randomUUID() }
    const result = await api.crmExecuteSample(action.id, { proposal_id: proposal.proposal_id, expected_decision_id: decision.decision_id, idempotency_key: retry.current.key })
    // A confirmed failed receipt can start a distinct explicit retry. Unknown
    // outcomes keep the same key until their immutable receipt is recovered.
    if (result.status === 'SAMPLE_FAILED') retry.current = undefined
    return `${result.replayed ? 'Saved receipt recovered. ' : ''}${result.detail}`
  })

  return <div aria-busy={busy}>
    <p>Prepare and review exact follow-up fields. External CRM writes are disabled in this environment.</p>
    <div className="card-actions"><Button disabled={busy} onClick={() => void prepare()}>Prepare exact CRM proposal</Button><Button disabled={busy} onClick={() => setReload(value => value + 1)}>Refresh CRM history</Button></div>
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
    {!history && !error && <p role="status">Loading saved CRM proposals…</p>}
    {history && proposals.length === 0 && <p>No saved proposal for this Action.</p>}
    {proposal && <>
      <label>Saved proposal<select value={proposal.proposal_id} onChange={event => setSelectedId(event.target.value)} disabled={busy}>{proposals.map((item, index) => <option key={item.proposal_id} value={item.proposal_id}>Proposal {index + 1} · Action version {item.action_version}{item.proposal_id === history?.current_proposal_id ? ' · current' : ' · historical'}</option>)}</select></label>
      <h4>{proposal.destination_label}</h4>
      {!current && <p role="status">This proposal is historical or the Action changed. Prepare and review a new proposal before approval or execution.</p>}
      <dl>{Object.entries(proposal.payload).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{Array.isArray(value) ? value.join(', ') || 'Not supplied' : value ?? 'Not supplied'}</dd></div>)}</dl>
      {proposal.blockers.length > 0 && <ul aria-label="CRM proposal blockers">{proposal.blockers.map(item => <li key={item}>{item}</li>)}</ul>}
      <p>Proposal approval: {decision ? presentationLabel(decision.decision, 'workflow') : 'Awaiting manager review'}</p>
      {manager ? <div className="card-actions"><Button disabled={busy || !current || proposal.blockers.length > 0 || decision?.decision === 'APPROVED'} onClick={() => void approve('APPROVED')}>Approve exact proposal</Button><Button disabled={busy || !current || proposal.blockers.length > 0 || decision?.decision === 'REJECTED'} onClick={() => void approve('REJECTED')}>Reject exact proposal</Button><Button disabled={busy || !current || proposal.blockers.length > 0 || decision?.decision !== 'APPROVED' || lastAttempt?.status === 'SAMPLE_COMPLETED'} onClick={() => void attempt()}>{lastAttempt?.status === 'SAMPLE_FAILED' ? 'Retry controlled attempt' : 'Run approved controlled attempt'}</Button></div> : <p>A Manager must approve this exact proposal and confirm the controlled attempt.</p>}
      {lastAttempt && <p>Latest receipt: {lastAttempt.status === 'SAMPLE_COMPLETED' ? 'Controlled attempt completed — no external CRM write' : 'Controlled attempt failed'} · {lastAttempt.detail}</p>}
      <details><summary>Mapping, versions and immutable receipts</summary><CanonicalRecord value={{ proposal_id: proposal.proposal_id, action_version: proposal.action_version, commercial_revision: proposal.commercial_revision, mapping: proposal.mapping, mapping_revision: proposal.mapping_revision, decisions, attempts }} /></details>
      {Boolean(history?.earlier_event_count) && <p>{history?.earlier_event_count} earlier audit events are retained; this view shows the latest 100.</p>}
    </>}
  </div>
}
