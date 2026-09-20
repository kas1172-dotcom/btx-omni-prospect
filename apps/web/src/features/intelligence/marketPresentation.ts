import type { MarketMetadata, MarketPoint, MarketSeries, MarketTransformation } from '../../types/markets'

export const transformationLabel: Record<MarketTransformation, string> = {
  LEVEL: 'Production index · 2017=100',
  MOM_PERCENT: 'Month-over-month change · percent',
  YOY_PERCENT: 'Year-over-year change · percent',
}

const numericPoints = (points: MarketPoint[]) => points.filter(point => point.value != null).map(point => ({ ...point, numeric: Number(point.value) })).filter(point => Number.isFinite(point.numeric))
const cadenceLabel = (value: string) => ({ MONTHLY: 'Monthly', QUARTERLY: 'Quarterly', ANNUAL: 'Annual' })[value] ?? value
const geographyLabel = (value: string) => ({ US_NATIONAL_EXCLUDING_TERRITORIES: 'United States · national, excluding territories', US_NATIONAL: 'United States · national' })[value] ?? value
const unitLabel = (value: string) => ({ INDEX: 'Index', PERCENT: 'Percent', DOLLARS: 'US dollars' })[value] ?? value

export function marketDecision(series: MarketSeries, transformation: MarketTransformation) {
  const values = numericPoints(series.points)
  const latest = values.at(-1)
  const previous = values.at(-2)
  const delta = latest && previous ? latest.numeric - previous.numeric : undefined
  const direction = !latest ? 'Direction unavailable' : transformation === 'LEVEL'
    ? delta == null ? 'Change unavailable' : delta > 0 ? 'Higher than the prior month' : delta < 0 ? 'Lower than the prior month' : 'Unchanged from the prior month'
    : latest.numeric > 0 ? 'Positive change' : latest.numeric < 0 ? 'Negative change' : 'No change'
  return {
    latest, direction, delta, measure: series.metadata.title,
    unit: transformation === 'LEVEL' ? `${unitLabel(series.metadata.unit)}${series.metadata.index_base ? ` · ${series.metadata.index_base}` : ''}` : 'Percent change',
    cadence: cadenceLabel(series.metadata.frequency), geography: geographyLabel(series.metadata.geography), limitation: series.metadata.limitation,
    commercialMeaning: 'This national manufacturing series can guide a market-level conversation and follow-up research. It does not establish an account order, regional demand, facility activity or BTX capacity.',
    nextAction: 'Compare the market movement with account history, program evidence, and active commercial work before changing seller priority.',
  }
}

export function comparisonCompatibility(primary: MarketMetadata, candidate: MarketMetadata): { compatible: boolean; reason: string } {
  const mismatches = [primary.unit === candidate.unit ? undefined : 'unit', primary.frequency === candidate.frequency ? undefined : 'cadence', primary.geography === candidate.geography ? undefined : 'geography', primary.seasonal_adjustment === candidate.seasonal_adjustment ? undefined : 'seasonal adjustment'].filter(Boolean)
  return mismatches.length ? { compatible: false, reason: `Comparison unavailable because ${mismatches.join(', ')} do not match and no approved normalization method is available.` } : { compatible: true, reason: 'Series share unit, cadence, geography and seasonal-adjustment basis.' }
}
