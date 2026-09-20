import { WhyThis } from './SupportingEvidence'
import type { CSSProperties } from 'react'
import './scoreSummary.css'
import { scorePolarity, type ScoreSummaryModel } from './scoreSummaryModel'

const words = (value: string) => value.replaceAll('_', ' ').toLocaleLowerCase().replace(/^./, letter => letter.toUpperCase())
const displayValue = (value: ScoreSummaryModel['value']) => {
  if (value == null || value === '') return 'Unavailable'
  const numeric = typeof value === 'number' ? value : /^\d+(?:\.\d+)?$/.test(value) ? Number(value) : null
  return numeric == null ? value : `${numeric.toLocaleString('en-US', { maximumFractionDigits: 2 })}/100`
}
const sellerInterpretation = (value: string) => value.startsWith('IMPLEMENTATION_INTERPRETATION_PENDING_JAMIE_CALIBRATION:')
  ? 'Provisional interpretation pending BTX business calibration; the deterministic score and its inputs remain unchanged.'
  : value
const coverageText = (coverage?: ScoreSummaryModel['coverage']) => {
  if (!coverage) return 'Completeness has not been calculated.'
  if (coverage.ratio != null) return `${Math.round(Number(coverage.ratio) * 100)}% weighted evidence coverage.`
  if (coverage.present != null && coverage.applicable != null) return `${coverage.present} of ${coverage.applicable} applicable inputs supported.`
  return 'Completeness has not been calculated.'
}

export function ScoreSummary({ model, compact = false }: { model: ScoreSummaryModel; compact?: boolean }) {
  const available = model.value != null && model.value !== ''
  const polarity = scorePolarity(model.family)
  const healthReasons = model.family.toLowerCase() === 'customer health' ? [...(model.limitingFactors ?? []), ...(model.positiveFactors ?? [])].filter(factor => factor.detail).slice(0, 2) : []
  const raw = model.numericValue ?? model.value
  const numeric = raw != null && /^\d+(?:\.\d+)?$/.test(String(raw)) ? Number(raw) : null
  // Continuous presentation only: no new thresholds, classifications or scores.
  const hue = numeric != null && numeric >= 0 && numeric <= 100 && polarity !== 'neutral' ? (polarity === 'risk' ? 100 - numeric : numeric) * 1.2 : null
  const style = hue == null ? undefined : { '--score-accent': `hsl(${hue} 65% 28%)` } as CSSProperties
  return <article style={style} className={`score-summary score-polarity-${available ? polarity : 'neutral'} ${compact ? 'score-summary-compact' : ''}`} aria-label={`${model.family} score summary`}>
    <div className="score-summary-heading"><span>{model.family}</span><strong>{displayValue(model.value)}</strong></div>
    {!compact && <>{healthReasons.length ? <ul className="score-key-reasons">{healthReasons.map(factor => <li key={factor.label}><strong>{factor.label}:</strong> {factor.detail}</li>)}</ul> : <p>{available ? sellerInterpretation(model.interpretation) : 'A score is not available from the current supported inputs.'}</p>}{available && polarity !== 'neutral' && <small>{polarity === 'risk' ? 'Higher values indicate greater risk.' : 'Higher values indicate a stronger result.'}</small>}</>}
    {!compact && <WhyThis>
      <p><strong>{model.subject}</strong>{model.asOf ? ` · As of ${model.asOf}` : ''}</p><p>{model.decision}</p>
      <p>{sellerInterpretation(model.interpretation)}</p>
      <p className="score-summary-coverage"><strong>Data Coverage</strong> · {coverageText(model.coverage)} Coverage describes completeness and never raises this decision score.</p>
      {model.numericValue != null && <p>Calculated result: {model.numericValue}/100. This does not change eligibility or override a mandatory constraint.</p>}
      {!!model.positiveFactors?.length && <section><h4>Factors driving this result</h4><ul>{model.positiveFactors.map(factor => <li key={factor.label}><strong>{factor.label}</strong>{factor.value != null ? ` · ${factor.value}` : ''}<span>{factor.detail}</span></li>)}</ul></section>}
      {!!model.limitingFactors?.length && <section><h4>Limiting factors</h4><ul>{model.limitingFactors.map(factor => <li key={factor.label}><strong>{factor.label}</strong>{factor.value != null ? ` · ${factor.value}` : ''}<span>{factor.detail}</span></li>)}</ul></section>}
      {!!model.missingInputs?.length && <section><h4>Missing required inputs</h4><ul>{model.missingInputs.map(input => <li key={input}>{words(input)}</li>)}</ul></section>}
      <p className="muted">The configured formula and source inputs are unchanged; this summary does not recalculate the score.{model.version ? ` Score model: ${words(model.version)}.` : ''}</p>
      {(model.technicalId || model.evidenceIds?.length) && <small>{model.technicalId ? `Decision record ${model.technicalId}. ` : ''}{model.evidenceIds?.length ? `${model.evidenceIds.length} supporting evidence record${model.evidenceIds.length === 1 ? '' : 's'}.` : ''}</small>}
    </WhyThis>}
  </article>
}
