import type { MonitorSignalBrief } from '../types/api'

export type AttentionLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'UNAVAILABLE'

export function assessmentAttention(brief?: MonitorSignalBrief): AttentionLevel {
  if (!brief || brief.analysis_status !== 'READY') return 'UNAVAILABLE'
  if (brief.priority_eligible) return 'HIGH'
  if (brief.commercial_relevance_state === 'REVIEW_REQUIRED') return 'MEDIUM'
  if (brief.commercial_relevance_state === 'INFORMATIONAL') return 'LOW'
  return 'UNAVAILABLE'
}
