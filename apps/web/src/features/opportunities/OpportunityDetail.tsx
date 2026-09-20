import { useRef, useState } from 'react'
import type { Opportunity } from '../../types/opportunities'
import type { WorkspaceLocation } from '../../app/navigation'
import { workspaceHash } from '../../app/navigation'
import { Drawer } from '../../components/UI'
import { ScoreSummary } from '../../components/ScoreSummary'
import { commercialDecisionSummary } from '../../components/scoreSummaryModel'
import { CommercialEvidence } from '../accounts/CommercialEvidence'
import { category, money, priorityOf, stageLabel, words } from './opportunityModel'

export function OpportunityDetail({ row, location, fixture, onClose, onPrevious, onNext }: { row: Opportunity; location: WorkspaceLocation; fixture: boolean; onClose: () => void; onPrevious?: () => void; onNext?: () => void }) {
  const close = useRef<HTMLButtonElement>(null)
  const [evidence, setEvidence] = useState(false)
  const p = priorityOf(row)
  const decision = row.opportunity_priority
  const sources = new Set([...decision.factors.flatMap(f => f.evidence_ids), ...(row.gates?.evidence_ids ?? [])])
  const labels: Record<string, string> = { program_durability: 'Program durability', btx_manufacturing_fit: 'BTX manufacturing fit', addressable_btx_work: 'Addressable BTX work', program_momentum: 'Program momentum', strategic_target_fit: 'Strategic target fit', btx_commercial_adjacency: 'BTX commercial adjacency' }
  return <Drawer open onClose={onClose} titleId="opp-detail-title" initialFocus={close} className="opp-detail">
    <div className="opp-sheet-handle" aria-hidden="true" />
    <header className="opp-detail-header"><div className="opp-detail-controls"><button aria-label="Previous opportunity" disabled={!onPrevious} onClick={onPrevious}>←</button><button aria-label="Next opportunity" disabled={!onNext} onClick={onNext}>→</button><button ref={close} aria-label="Close opportunity" onClick={onClose}>×</button></div><h2 id="opp-detail-title">{row.title}</h2><p><strong>{row.account_name}</strong><span className="opp-stage">{stageLabel(row.stage)}</span><span>{money(row.value_minor, row.currency)}</span><span>{category(row.market)}</span></p></header>
    <div className="opp-detail-body"><section className="opp-score-block"><div><strong>{p.text}</strong><span className={`opp-band opp-band-${p.tone}`}>{p.band}</span></div><p title={decision.configuration_version}>Data coverage {Math.round(Number(decision.data_coverage.ratio) * 100)}% · Scoring rules {decision.configuration_version === 'BTX_SCORING_RUBRIC_V2' ? 'v2.0' : decision.configuration_version}</p></section>
      <section><h3>Score factors</h3>{decision.factors.length ? decision.factors.map(f => <div className="opp-factor" key={f.key} title={f.reason}><span>{labels[f.key] ?? words(f.key)}</span><span className="opp-factor-track" aria-hidden="true">{f.points !== null && <span style={{ width: `${Number(f.points)}%` }} />}</span><strong>{f.contribution == null ? 'Unknown' : `${f.contribution} / ${f.weight}`}</strong><small>{f.reason}</small></div>) : <p>Factor detail not supplied.</p>}</section>
      <section><h3>Qualification</h3>{([['Qualified', row.qualification_status, row.gates?.qualification_checks], ['Durable', row.durability_status, row.gates?.durability_checks]] as const).map(([label, status, checks]) => <div className="opp-gate" key={label}><strong>{label}</strong><span className={`opp-status opp-status-${status === 'YES' ? 'durable' : status === 'NO' ? 'no' : 'unknown'}`}>{status === 'YES' ? 'Yes' : status === 'NO' ? 'No' : 'Unknown'}</span>{checks && Object.keys(checks).length ? <ul>{Object.entries(checks).map(([key, value]) => <li key={key}>{words(key)}: {value === true ? 'Yes' : value === false ? 'No' : 'Unknown'}</li>)}</ul> : <p>Supporting gate reasons not supplied.</p>}</div>)}</section>
      <section><h3>Business context</h3><p>{row.business_context || 'No business context recorded.'}</p></section>
      <section><h3>Open questions</h3>{row.material_uncertainties.length ? <ul>{row.material_uncertainties.map(q => <li key={q}>{q}</li>)}</ul> : <p>No open questions recorded.</p>}</section>
      <section><h3>Next step</h3><p>{row.next_action || 'No opportunity-specific next step recorded.'}</p></section>
      <section><button className="opp-evidence-trigger" aria-expanded={evidence} onClick={() => setEvidence(!evidence)}>Evidence <span>{sources.size} cited sources {evidence ? '⌃' : '⌄'}</span></button>{evidence && <div><p>Assessment date: {row.as_of} · Revision {row.revision}</p>{fixture ? <p>Illustrative development data. No canonical evidence record exists.</p> : <CommercialEvidence key={row.opportunity_id} accountId={row.account_id} recordId={row.source_record_id} />}{[row.pwin, row.delivery_feasibility].map(d => <ScoreSummary key={d.family} model={commercialDecisionSummary(d, row.title)} />)}</div>}</section>
    </div><footer className="opp-detail-footer"><button className="opp-primary" disabled={fixture} title={fixture ? 'Development examples are not real Omni context' : undefined} onClick={() => { onClose(); window.dispatchEvent(new Event('btx:open-omni')) }}>Ask Omni</button>{fixture ? <button disabled title="Development example has no canonical account">Open account</button> : <a href={workspaceHash({ surface: 'accounts', accountId: row.account_id, returnTo: location })}>Open account</a>}</footer>
  </Drawer>
}
