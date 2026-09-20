import type { CommercialDecision } from '../../types/decisions'
import { ScoreSummary } from '../../components/ScoreSummary'
import { commercialDecisionSummary } from '../../components/scoreSummaryModel'

export function ProfileHealth({ health, name }: { health?: CommercialDecision | null; name: string }) {
  return health ? <ScoreSummary model={commercialDecisionSummary(health, name, 'Review the health of the existing customer relationship')} />
    : <p>Customer Health needs commercial history. Attractiveness is assessed separately for each opportunity.</p>
}
