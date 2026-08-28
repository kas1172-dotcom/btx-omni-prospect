import type { MonitorSignalBrief } from '../types/api'
import { Button, Disclosure, EvidenceSource, State } from './UI'
import './signalBrief.css'

const dateLabel = (value?: string) => value ? new Date(value).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'Date unavailable'
const display = (value: string) => value.replaceAll('_', ' ').toLocaleLowerCase().replace(/^./, letter => letter.toUpperCase())
const modeLabel = (value: string) => ({ LIVE_PUBLIC: 'LIVE PUBLIC', CURATED_PUBLIC: 'CURATED PUBLIC', SANITIZED_REFERENCE: 'SANITIZED REFERENCE', SAMPLE: 'SAMPLE BTX CONTEXT' }[value] ?? display(value))

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
    {brief.summary_mode === 'GEMINI_ASSISTED' && <small>Language assisted; governed evidence unchanged.</small>}
    <Disclosure title="Evidence, why it matters, and next step">
      <div className="seller-signal-details">
        <p><strong>What happened:</strong> {brief.what_happened}</p>
        <p><strong>Why it may matter:</strong> {brief.why_it_may_matter}</p>
        <p><strong>What to watch:</strong> {brief.what_to_watch}</p>
        {brief.priority_reasons.length > 0 && <div><strong>Why watched:</strong><ul>{brief.priority_reasons.map(reason => <li key={`${reason.code}:${reason.source_system}:${reason.source_record_id ?? ''}`}>{reason.detail} <small>({display(reason.source_system)})</small></li>)}</ul></div>}
        {brief.recommended_action && <p><strong>Governed next step:</strong> {brief.recommended_action}</p>}
        {brief.missing_fields.length > 0 && <p><strong>Missing:</strong> {brief.missing_fields.join(', ')}</p>}
        <EvidenceSource title={brief.headline} source={brief.source_system} date={dateLabel(brief.publication_timestamp)} evidenceState={brief.resolution_state} validationState={brief.seller_promotion_state} url={brief.source_url} detail={`Evidence IDs: ${brief.evidence_ids.length ? brief.evidence_ids.join(', ') : 'Unavailable'}`} />
      </div>
    </Disclosure>
    {onUseInOmni && <div className="card-actions"><Button aria-pressed={selected} variant={selected ? 'primary' : 'secondary'} onClick={() => onUseInOmni(brief)}>{selected ? 'Clear Omni event' : 'Use in Omni'}</Button></div>}
  </article>
}
