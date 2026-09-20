import type { Opportunity } from '../../types/opportunities'
import { priorityOf, statusOf } from './opportunityModel'

export function PriorityCell({ row, showBand = false }: { row: Opportunity; showBand?: boolean }) {
  const p = priorityOf(row)
  return <span className={`opp-priority opp-priority-${p.tone}`} aria-label={`Priority ${p.text}. ${p.band}`}><span className="opp-priority-number">{p.text}</span><span className="opp-priority-track" aria-hidden="true">{p.complete ? <span style={{ width: `${p.score}%` }} /> : p.low !== null && p.high !== null ? <span className="opp-range" style={{ left: `${p.low}%`, width: `${p.high - p.low}%` }} /> : null}</span>{showBand && <small>{p.band}</small>}</span>
}
export function OpportunityStatus({ row }: { row: Opportunity }) {
  const status = statusOf(row)
  return <span className={`opp-status opp-status-${status.tone}`}>{status.label}</span>
}
