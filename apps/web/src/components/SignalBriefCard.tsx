import type { MonitorSignalBrief } from '../types/api'
import { Button, Disclosure, EvidenceSource, State } from './UI'
import { GovernedExplanationDisclosure } from './GovernedExplanationDisclosure'
import { EvidencePassages } from './EvidencePassages'
import './signalBrief.css'

const dateLabel = (value?: string) => value ? new Date(value).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'Date unavailable'
const display = (value: string) => value.replaceAll('_', ' ').toLocaleLowerCase().replace(/^./, letter => letter.toUpperCase())
const modeLabel = (value: string) => ({ LIVE_PUBLIC: 'CONNECTED PUBLIC', CURATED_PUBLIC: 'CURATED PUBLIC', SANITIZED_REFERENCE: 'REFERENCE EVIDENCE', SAMPLE: 'BTX COMMERCIAL CONTEXT' }[value] ?? display(value))

export function SignalBriefCard({ brief, accountName, onAccount, onUseInOmni, selected = false }: { brief: MonitorSignalBrief; accountName?: (id: string) => string; onAccount?: (id: string) => void; onUseInOmni?: (brief: MonitorSignalBrief) => void; selected?: boolean }) {
  const accountId = brief.canonical_account_ids[0]
  const eventDate = brief.relevant_event_timestamp ?? brief.publication_timestamp
  return <article className="seller-signal-brief">
    <div className="seller-signal-head">
      <div><span className="eyebrow">{brief.event_timing === 'UPCOMING' ? 'Upcoming radar' : 'Signal brief'}</span><h3>{brief.headline}</h3></div>
      <div className="seller-signal-states"><State value={modeLabel(brief.data_mode)} /><State value={display(brief.freshness)} /></div>
    </div>
    <div className="seller-signal-meta">
      {accountId && <Button variant="ghost" onClick={() => onAccount?.(accountId)}>{accountName?.(accountId) ?? 'Open Customer'}</Button>}
      {brief.markets.map(market => <State key={market} value={market} />)}
      <span>{brief.event_timing === 'UPCOMING' ? 'Event' : 'Published'}: {dateLabel(eventDate)}</span>
    </div>
    <p>{brief.seller_summary}</p>
    {brief.analysis_status && brief.analysis_status !== 'READY' && <p className="notice">Analysis is incomplete. The source remains available, but no completed commercial recommendation is shown.</p>}
    {brief.commercial_relevance_state === 'INFORMATIONAL' && <small>Informational update · no established commercial priority</small>}
    {brief.summary_mode === 'GEMINI_ASSISTED' && <small>Language assisted; governed evidence unchanged.</small>}
    {brief.signal_confidence && <Disclosure title={`Signal confidence · ${brief.signal_confidence.score == null ? 'More evidence needed' : `${brief.signal_confidence.score}/100`}`}>
      <div className="seller-signal-details">
        <p>Confidence describes this assertion, not its commercial value or risk severity.</p>
        <p>{brief.signal_confidence.data_coverage.present} of {brief.signal_confidence.data_coverage.applicable} required fields are supported. POC calibration is provisional.</p>
        <ul>{brief.signal_confidence.factors.map(factor => <li key={factor.key}>
          <strong>{display(factor.key)}:</strong> {factor.points == null ? 'Unknown' : `${factor.points}/100`} · {factor.reason}
          {factor.evidence_ids.length > 0 && <small> Evidence: {factor.evidence_ids.join(', ')}</small>}
        </li>)}</ul>
        <small>{brief.signal_confidence.decision_id} · {brief.signal_confidence.configuration_version} · {brief.signal_confidence.input_configuration_version}</small>
      </div>
    </Disclosure>}
    {brief.risk_severity && <Disclosure title={`Risk severity · ${brief.risk_severity.score == null ? 'More evidence needed' : `${brief.risk_severity.score}/100`}`}>
      <div className="signal-score-detail">
        <p><strong>{brief.risk_severity.disposition.replaceAll('_', ' ')}</strong> · severity remains separate from evidence confidence.</p>
        <p>{brief.risk_severity.data_coverage.present} of {brief.risk_severity.data_coverage.applicable} applicable risk fields are supported.</p>
        <ul>{brief.risk_severity.factors.map(factor => <li key={factor.key}><strong>{factor.key.replaceAll('_', ' ')}</strong>: {factor.reason}</li>)}</ul>
      </div>
    </Disclosure>}
    {brief.technical_opportunity && <Disclosure title="Potential BTX Technical Fit">
      <div className="seller-signal-details technical-fit">
        {brief.technical_opportunity.event_summary && <p>{brief.technical_opportunity.event_summary}</p>}
        {brief.technical_opportunity.program_candidates.length > 0 && <div><strong>Program / product</strong><ul>{[...brief.technical_opportunity.program_candidates, ...brief.technical_opportunity.product_candidates].map((item, index) => <li key={`candidate-${index}`}>{item.name} · {display(item.basis)}</li>)}</ul></div>}
        {brief.technical_opportunity.technical_systems.length > 0 && <div><strong>Technical context</strong><ul>{brief.technical_opportunity.technical_systems.map((item, index) => <li key={`system-${index}`}>{item.name} · {display(item.basis)}</li>)}</ul></div>}
        {brief.technical_opportunity.matches.length ? brief.technical_opportunity.matches.map((match, index) => <article key={`${match.candidate_name}:${index}`}>
          <p><strong>{match.candidate_name}</strong> · <span>{display(match.basis)}</span></p>
          {match.status === 'MATCHED' ? <>
            <p>Controlled BTX match: {match.component_name ?? 'Available'}</p>
            <p>Applicable BU{match.business_units.length === 1 ? '' : 's'}: {match.business_units.map(unit => unit.name).join(', ') || 'Unavailable'}</p>
          </> : <p>{match.status === 'NO_MATCH' ? 'No controlled BTX capability match identified.' : match.status === 'POSSIBLE_MATCH_REVIEW_REQUIRED' ? 'Controlled taxonomy review required before a BTX match is asserted.' : 'Controlled BTX taxonomy is not specific enough for a match.'}</p>}
        </article>) : <p>{brief.technical_opportunity.provider_status === 'AVAILABLE' ? 'No manufactured component candidates were identified from the supplied public evidence.' : 'Technical decomposition is unavailable; the governed public signal remains available.'}</p>}
        {brief.technical_opportunity.uncertainties.length > 0 && <div><strong>Uncertainties</strong><ul>{brief.technical_opportunity.uncertainties.map(item => <li key={item}>{item}</li>)}</ul></div>}
        <small>{brief.technical_opportunity.disclosure}</small>
        <GovernedExplanationDisclosure title="Why this technical fit may matter" explanation={brief.technical_opportunity.governed_explanation} />
      </div>
    </Disclosure>}
    <Disclosure title="Evidence, why it matters, and next step">
      <div className="seller-signal-details">
        <p><strong>What happened:</strong> {brief.what_happened}</p>
        <p><strong>Why it may matter:</strong> {brief.why_it_may_matter}</p>
        <p><strong>What to watch:</strong> {brief.what_to_watch}</p>
        {brief.action_rationale && <p><strong>Action rationale:</strong> {brief.action_rationale}</p>}
        {!!brief.material_uncertainties?.length && <div><strong>What remains uncertain:</strong><ul>{brief.material_uncertainties.map(item => <li key={item}>{item}</li>)}</ul></div>}
        {brief.priority_reasons.length > 0 && <div><strong>Why watched:</strong><ul>{brief.priority_reasons.map(reason => <li key={`${reason.code}:${reason.source_system}:${reason.source_record_id ?? ''}`}>{reason.detail} <small>({display(reason.source_system)})</small></li>)}</ul></div>}
        {brief.recommended_action && <p><strong>Governed next step:</strong> {brief.recommended_action}</p>}
        {brief.missing_fields.length > 0 && <p><strong>Missing:</strong> {brief.missing_fields.join(', ')}</p>}
        <EvidenceSource title={brief.headline} source={brief.source_system} date={dateLabel(brief.publication_timestamp)} evidenceState={brief.resolution_state} validationState={brief.seller_promotion_state} url={brief.source_url} detail={`Evidence IDs: ${brief.evidence_ids.length ? brief.evidence_ids.join(', ') : 'Unavailable'}`} />
        {brief.references?.filter(item => item.url && item.url !== brief.source_url).map(item => <EvidenceSource key={item.evidence_id} title={item.title} source="Public source" date={dateLabel(item.publication_date ?? undefined)} evidenceState="CITED" url={item.url} detail="Supporting passage used in this briefing" />)}
        {brief.data_mode === 'LIVE_PUBLIC' && <EvidencePassages key={brief.id} eventId={brief.id} />}
      </div>
    </Disclosure>
    {onUseInOmni && <div className="card-actions"><Button aria-pressed={selected} variant={selected ? 'primary' : 'secondary'} onClick={() => onUseInOmni(brief)}>{selected ? 'Clear Omni event' : 'Use in Omni'}</Button></div>}
  </article>
}
