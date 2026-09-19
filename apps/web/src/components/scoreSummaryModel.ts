import type { AttractivenessProjection, ProspectFitProjection } from '../types/api'
import type { CommercialDecision } from '../types/decisions'

export type ScoreFactor = { label: string; detail: string; value?: string | number | null; evidenceIds?: string[] }
export type ScoreSummaryModel = { family: string; decision: string; subject: string; value: string | number | null; numericValue?: string | number | null; interpretation: string; version?: string; asOf?: string; positiveFactors?: ScoreFactor[]; limitingFactors?: ScoreFactor[]; missingInputs?: string[]; coverage?: { present?: number; applicable?: number; ratio?: string | number }; evidenceIds?: string[]; technicalId?: string }
const words = (value?: string) => (value || 'decision score').replaceAll('_', ' ').toLocaleLowerCase().replace(/^./, letter => letter.toUpperCase())
export function scoreValue(score: string | number | null, range?: { low: string | number; high: string | number }): string | number | null {
  if (score != null) return score
  if (!range) return null
  const low = Number(range.low), high = Number(range.high)
  if (!Number.isFinite(low) || !Number.isFinite(high) || low < 0 || high > 100 || low > high) return null
  return `${low.toLocaleString('en-US', { maximumFractionDigits: 2 })}–${high.toLocaleString('en-US', { maximumFractionDigits: 2 })}/100 · incomplete`
}

export function commercialDecisionSummary(decision: CommercialDecision, subject: string, supportedDecision?: string): ScoreSummaryModel {
  const factors = decision.factors.map(factor => ({ label: words(factor.key), detail: factor.reason, value: factor.points, evidenceIds: factor.evidence_ids }))
  return { family: words(decision.family), decision: supportedDecision ?? `Use ${words(decision.family)} when reviewing this account`, subject, value: familyValue(decision), numericValue: decision.score, interpretation: decision.interpretation ?? 'No additional account-specific interpretation is available.', version: decision.configuration_version, asOf: decision.as_of, positiveFactors: factors.filter(factor => factor.value != null && Number(factor.value) > 0), limitingFactors: factors.filter(factor => factor.value == null || Number(factor.value) <= 0), missingInputs: decision.data_coverage.missing_fields ?? [], coverage: decision.data_coverage, evidenceIds: [...new Set(decision.factors.flatMap(factor => factor.evidence_ids ?? []))], technicalId: decision.decision_id }
}

export function familyValue(decision: Pick<CommercialDecision, 'family' | 'score' | 'status' | 'score_range' | 'priority_rank'>): string | number | null {
  if (decision.family === 'action_priority') return decision.priority_rank ? `Queue position ${decision.priority_rank}` : null
  if (decision.status === 'BLOCKED') return 'Blocked'
  if (decision.status === 'INELIGIBLE') return 'Not applicable yet'
  if (decision.score == null) return scoreValue(null, decision.score_range)
  const score = Number(decision.score)
  if (decision.family === 'customer_health') return score >= 70 ? 'Healthy' : score >= 50 ? 'Watch' : score >= 30 ? 'At risk' : 'Critical'
  if (decision.family === 'delivery_feasibility') return score >= 93 ? 'A+' : score >= 85 ? 'A' : score >= 78 ? 'B+' : score >= 70 ? 'B' : score >= 55 ? 'C' : score >= 40 ? 'D' : 'F'
  if (decision.family === 'signal_confidence') return score >= 70 ? 'High' : score >= 40 ? 'Medium' : 'Low'
  return decision.score
}

export function attractivenessSummary(score: AttractivenessProjection, subject: string): ScoreSummaryModel {
  const factors = score.factors.map(factor => ({ label: words(factor.name), detail: factor.gaps.join(', ') || 'Supported by the available account evidence.', value: factor.score, evidenceIds: factor.evidence_ids }))
  return { family: 'Customer Attractiveness', decision: 'Prioritize account research and review', subject, value: scoreValue(score.score, score.status === 'UNAVAILABLE' ? undefined : score.score_range), interpretation: score.interpretation_note, version: score.configuration_version, positiveFactors: factors.filter(factor => factor.value != null && !score.factors.find(item => words(item.name) === factor.label)?.missing), limitingFactors: factors.filter(factor => factor.value == null || score.factors.find(item => words(item.name) === factor.label)?.missing), missingInputs: score.missingness, coverage: { ratio: score.coverage }, evidenceIds: score.evidence_ids }
}

export function prospectFitSummary(score: ProspectFitProjection, subject: string): ScoreSummaryModel {
  const value = score.score != null ? `${score.score}%` : (score.score_low != null && score.score_high != null ? `${score.score_low}–${score.score_high}% · incomplete` : null)
  const factors = score.factors.map(factor => ({ label: factor.label, detail: factor.reason, value: factor.points, evidenceIds: factor.evidence_ids }))
  return { family: score.name, decision: 'Decide whether this Prospect warrants further validation', subject, value, interpretation: score.interpretation, version: score.configuration_version, positiveFactors: factors.filter(factor => factor.value != null && Number(factor.value) > 0), limitingFactors: factors.filter(factor => factor.value == null || Number(factor.value) <= 0), missingInputs: score.missingness, coverage: { ratio: score.coverage }, evidenceIds: [...new Set(score.factors.flatMap(factor => factor.evidence_ids))] }
}
