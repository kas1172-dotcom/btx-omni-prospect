import { Disclosure } from './UI'
import './scoreSummary.css'
import type { ScoreSummaryModel } from './scoreSummaryModel'

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
  if (coverage.present != null && coverage.applicable != null) return `${coverage.present} of ${coverage.applicable} applicable inputs supported.`
  if (coverage.ratio != null) return `${Math.round(Number(coverage.ratio) * 100)}% of applicable inputs supported.`
  return 'Completeness has not been calculated.'
}

export function ScoreSummary({ model, compact = false }: { model: ScoreSummaryModel; compact?: boolean }) {
  const available = model.value != null && model.value !== ''
  return <article className={`score-summary ${compact ? 'score-summary-compact' : ''}`} aria-label={`${model.family} score summary`}>
    <div className="score-summary-heading"><span>{model.family}</span><strong>{displayValue(model.value)}</strong></div>
    {!compact && <><p className="score-summary-decision"><strong>Decision supported:</strong> {model.decision}</p><p>{available ? sellerInterpretation(model.interpretation) : 'A decision score is not available from the current supported inputs.'}</p><dl><div><dt>Subject</dt><dd>{model.subject}</dd></div>{model.asOf && <div><dt>As of</dt><dd>{model.asOf}</dd></div>}</dl></>}
    <p className="score-summary-coverage"><strong>Data Coverage</strong> · {coverageText(model.coverage)} Coverage describes completeness and never raises this decision score.</p>
    {!compact && <Disclosure title="Formula, inputs and supporting evidence">
      {!!model.positiveFactors?.length && <section><h4>Most important positive factors</h4><ul>{model.positiveFactors.map(factor => <li key={factor.label}><strong>{factor.label}</strong>{factor.value != null ? ` · ${factor.value}` : ''}<span>{factor.detail}</span></li>)}</ul></section>}
      {!!model.limitingFactors?.length && <section><h4>Limiting factors</h4><ul>{model.limitingFactors.map(factor => <li key={factor.label}><strong>{factor.label}</strong>{factor.value != null ? ` · ${factor.value}` : ''}<span>{factor.detail}</span></li>)}</ul></section>}
      {!!model.missingInputs?.length && <section><h4>Missing required inputs</h4><ul>{model.missingInputs.map(input => <li key={input}>{words(input)}</li>)}</ul></section>}
      <p className="muted">The configured formula and source inputs are unchanged; this summary does not recalculate the score.{model.version ? ` Score model: ${words(model.version)}.` : ''}</p>
      {(model.technicalId || model.evidenceIds?.length) && <small>{model.technicalId ? `Decision record ${model.technicalId}. ` : ''}{model.evidenceIds?.length ? `${model.evidenceIds.length} supporting evidence record${model.evidenceIds.length === 1 ? '' : 's'}.` : ''}</small>}
    </Disclosure>}
  </article>
}
