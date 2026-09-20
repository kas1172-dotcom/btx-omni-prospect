import type { CommandPriorityItem, MonitorSignalBrief, OmniAssessmentSelection } from '../types/api'
import { Button, Disclosure, EvidenceSource, State } from './UI'
import { GovernedExplanationDisclosure } from './GovernedExplanationDisclosure'
import { EvidencePassages } from './EvidencePassages'
import { TechnicalDecompositionSection } from './TechnicalDecompositionSection'
import { SupportingEvidence, WhyThis } from './SupportingEvidence'
import { RelatedBtxActivity } from './RelatedBtxActivity'
import { ScoreSummary } from './ScoreSummary'
import { commercialDecisionSummary } from './scoreSummaryModel'
import { AttentionBadge } from './AttentionBadge'
import { assessmentAttention } from './attentionModel'
import { attentionFor } from '../features/today/todayModel'
import './signalBrief.css'

const dateLabel = (value?: string) => value ? new Date(value).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'Date unavailable'
const display = (value: string) => value.replaceAll('_', ' ').toLocaleLowerCase().replace(/^./, letter => letter.toUpperCase())
export function SignalBriefCard({ brief, priority, accountName, onAccount, onUseInOmni, selected = false }: { brief: MonitorSignalBrief; priority?: CommandPriorityItem; accountName?: (id: string) => string; onAccount?: (id: string, assessment?: OmniAssessmentSelection) => void; onUseInOmni?: (brief: MonitorSignalBrief) => void; selected?: boolean }) {
  const accountId = brief.canonical_account_ids[0]
  const eventDate = brief.relevant_event_timestamp ?? brief.publication_timestamp
  const records = brief.evidence_package?.commercial_records ?? []
  const evidenceCount = new Set([...(brief.evidence_ids ?? []), ...(brief.references ?? []).map(item => item.evidence_id), ...records.map(item => item.record_id)]).size
  const coverage = brief.signal_confidence?.data_coverage
  const knowledgeLabel = !coverage ? 'Still being assessed' : Number(coverage.ratio) >= .8 ? 'Substantial' : Number(coverage.ratio) >= .5 ? 'Partial' : 'Limited'
  const attention = priority ? attentionFor(priority) : assessmentAttention(brief)
  return <article className={`seller-signal-brief attention-${attention.toLocaleLowerCase()}`}>
    <div className="seller-signal-head">
      <div><span className="eyebrow">{brief.event_timing === 'UPCOMING' ? 'Upcoming radar' : 'Signal brief'}</span><h3>{brief.headline}</h3></div>
      <AttentionBadge level={attention} />
    </div>
    <div className="seller-signal-meta">
      {accountId && <Button variant="ghost" onClick={() => onAccount?.(accountId, brief.assessment_id && brief.assessment_version ? { assessment_id: brief.assessment_id, assessment_version: brief.assessment_version, event_id: brief.id, account_id: accountId } : undefined)}>{accountName?.(accountId) ?? 'Open organization'}</Button>}
      {brief.markets.map(market => <State key={market} value={market} />)}
      <span>{brief.event_timing === 'UPCOMING' ? 'Event' : 'Published'}: {dateLabel(eventDate)}</span>
    </div>
    <div className="seller-signal-decision">
      {brief.seed_context && <section aria-label="Curated sample provenance">
        <span>{brief.seed_context.seed_type} — not a live monitor run</span>
        <p>{brief.seed_context.publisher}; retrieved {brief.seed_context.retrieval_date}. Site: {brief.seed_context.entity.site} ({brief.seed_context.entity.site_status.replaceAll('_', ' ')}).</p>
        <p>Need: {brief.seed_context.gates.need}. Publication: {brief.seed_context.gates.publication}. Contact gap: {brief.seed_context.contact_gap.role} ({brief.seed_context.contact_gap.state}).</p>
        <p><strong>{brief.seed_context.fit_hypothesis.label}:</strong> {brief.seed_context.fit_hypothesis.reasoning}</p>
        <ul>{brief.seed_context.routes.map(edge => <li key={`${edge.from}:${edge.to}`}><strong>{edge.state.replaceAll('_', ' ')}</strong>: {edge.from} → {edge.to}. {edge.reason}</li>)}</ul>
        <p>What would change the result: {brief.seed_context.what_would_change_result.join(' ')}</p>
      </section>}
      <section><span>What changed</span><p>{brief.what_happened}</p></section>
      <section><span>Why it may matter</span><p>{brief.why_it_may_matter} <WhyThis>{brief.action_rationale ?? brief.what_to_watch}</WhyThis></p></section>
      <section className="seller-signal-action" aria-label="Recommended next action"><span>Next decision</span><p>{brief.recommended_action ?? 'Keep this informational; no seller action is supported yet.'}</p></section>
    </div>
    {!!brief.material_uncertainties?.length && <p className="seller-signal-uncertainty"><strong>Material uncertainty — still unconfirmed:</strong> {brief.material_uncertainties[0]}</p>}
    {brief.analysis_status === 'PENDING_ANALYSIS' && <p className="notice">Analysis pending{brief.missing_fields.length ? `: ${brief.missing_fields.join(', ')}` : ''}</p>}
    {brief.analysis_status === 'INCOMPLETE' && <p className="notice">Analysis incomplete: no public evidence attached yet{brief.missing_fields.length ? `. Missing: ${brief.missing_fields.join(', ')}` : ''}</p>}
    {brief.commercial_relevance_state === 'INFORMATIONAL' && <small>Informational update · no established commercial priority</small>}
    <SupportingEvidence count={evidenceCount} investigationKey={`${brief.assessment_id ?? brief.id}:${brief.assessment_version ?? 0}`}>
      <section><h4>What we know: {knowledgeLabel}</h4><p>{coverage ? `${coverage.present} of ${coverage.applicable} applicable evidence fields are supported. Coverage describes completeness, not opportunity quality.` : 'Evidence completeness has not been calculated.'}</p></section>
      {brief.signal_confidence && <ScoreSummary model={{ ...commercialDecisionSummary(brief.signal_confidence, brief.headline, 'Judge how strongly the collected evidence supports this signal'), family: 'Signal Confidence', interpretation: `${brief.signal_confidence.interpretation ? `${brief.signal_confidence.interpretation} ` : ''}Confidence describes evidence support, not commercial value, qualification or technical fit.`, version: `${brief.signal_confidence.configuration_version} · inputs ${brief.signal_confidence.input_configuration_version}` }} />}
    {brief.risk_severity && <Disclosure title={`Risk severity · ${brief.risk_severity.score == null ? 'More evidence needed' : `${brief.risk_severity.score}/100`}`}>
      <div className="signal-score-detail">
        <p><strong>{brief.risk_severity.disposition.replaceAll('_', ' ')}</strong> · severity remains separate from evidence confidence.</p>
        <p>{brief.risk_severity.data_coverage.present} of {brief.risk_severity.data_coverage.applicable} applicable risk fields are supported.</p>
        <ul>{brief.risk_severity.factors.map(factor => <li key={factor.key}><strong>{factor.key.replaceAll('_', ' ')}</strong>: {factor.reason}</li>)}</ul>
      </div>
    </Disclosure>}
      {brief.technical_opportunity && <Disclosure title="Program, components and possible BTX fit">
      <div className="seller-signal-details technical-fit">
        <TechnicalDecompositionSection technical={brief.technical_opportunity} />
        {[...brief.technical_opportunity.program_candidates, ...brief.technical_opportunity.product_candidates, ...brief.technical_opportunity.technical_systems].length > 0 && <div><strong>Additional technical candidates</strong><ul>{[...brief.technical_opportunity.program_candidates, ...brief.technical_opportunity.product_candidates, ...brief.technical_opportunity.technical_systems].map((item, index) => <li key={`${item.name}:${index}`}>{item.name} · {display(item.basis)}</li>)}</ul></div>}
        {brief.technical_opportunity.matches.map((match, index) => <div key={`${match.candidate_name}:${index}`}>
          {match.status === 'MATCHED' ? <><p><strong>Controlled BTX match:</strong> {match.component_name ?? match.candidate_name} · {display(match.basis)}. This remains a fit hypothesis, not evidence of program participation.</p><p><strong>Applicable BU:</strong> {match.business_units.map(unit => unit.name).join(', ') || 'Validation required'}</p></> : <p>{match.status === 'NO_MATCH' ? 'No controlled BTX capability match identified.' : match.status === 'POSSIBLE_MATCH_REVIEW_REQUIRED' ? 'Controlled taxonomy review required before a BTX match is asserted.' : 'Controlled BTX taxonomy is not specific enough for a match.'}</p>}
        </div>)}
        <small>{brief.technical_opportunity.disclosure}</small>
        <GovernedExplanationDisclosure title="Why this technical fit may matter" explanation={brief.technical_opportunity.governed_explanation} />
      </div>
      </Disclosure>}
      <section><h4>Related BTX records</h4>{accountId ? <RelatedBtxActivity accountId={accountId} records={records} /> : <p>No canonical organization is resolved for internal-record review.</p>}</section>
      <Disclosure title="Sources, determination and validation history">
      <div className="seller-signal-details">
        <p><strong>What happened:</strong> {brief.what_happened}</p>
        <p><strong>Why it may matter:</strong> {brief.why_it_may_matter}</p>
        <p><strong>What to watch:</strong> {brief.what_to_watch}</p>
        {brief.action_rationale && <p><strong>Action rationale:</strong> {brief.action_rationale}</p>}
        {!!brief.material_uncertainties?.length && <div><strong>What remains uncertain:</strong><ul>{brief.material_uncertainties.map(item => <li key={item}>{item}</li>)}</ul></div>}
        {brief.priority_reasons.length > 0 && <div><strong>Why watched:</strong><ul>{brief.priority_reasons.map(reason => <li key={`${reason.code}:${reason.source_system}:${reason.source_record_id ?? ''}`}>{reason.detail} <small>({display(reason.source_system)})</small></li>)}</ul></div>}
        {brief.recommended_action && <p><strong>Next step:</strong> {brief.recommended_action}</p>}
        {brief.missing_fields.length > 0 && <p><strong>Missing:</strong> {brief.missing_fields.join(', ')}</p>}
        <EvidenceSource title={brief.headline} source={brief.source_system} date={dateLabel(brief.publication_timestamp)} evidenceState="Source reviewed" url={brief.source_url} detail="Primary public source for this assessment" />
        {brief.references?.filter(item => item.url && item.url !== brief.source_url).map(item => <EvidenceSource key={item.evidence_id} title={item.title} source="Public source" date={dateLabel(item.publication_date ?? undefined)} evidenceState="CITED" url={item.url} detail="Supporting passage used in this briefing" />)}
        {brief.data_mode === 'LIVE_PUBLIC' && <EvidencePassages key={brief.id} eventId={brief.id} />}
      </div>
      </Disclosure>
    </SupportingEvidence>
    {onUseInOmni && <div className="card-actions"><Button aria-pressed={selected} variant={selected ? 'primary' : 'secondary'} onClick={() => onUseInOmni(brief)}>{selected ? 'Clear Omni event' : 'Use in Omni'}</Button></div>}
  </article>
}
