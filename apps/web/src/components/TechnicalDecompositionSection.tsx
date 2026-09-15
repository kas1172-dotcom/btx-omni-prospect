import type { TechnicalCandidate, TechnicalOpportunity } from '../types/api'
import { Empty, EvidenceSource, State } from './UI'

const label = (value?: string) => (value ?? 'Unavailable').replaceAll('_', ' ').toLowerCase().replace(/^./, character => character.toUpperCase())
const layerLabel = (value?: string) => ({
  ANNOUNCED_SCOPE: 'Confirmed in this announcement',
  SUPPORTED_PROGRAM_ARCHITECTURE: 'Supported program architecture',
  BTX_FIT_HYPOTHESIS: 'Possible BTX fit — validation required',
}[value ?? ''] ?? label(value))
const citationDate = (provenance?: string | null) => {
  const value = provenance?.split('|')[1]
  return value && value !== 'date unavailable' ? value : undefined
}

function Branch({ component, childrenByParent, hypotheses }: { component: TechnicalCandidate; childrenByParent: Map<string, TechnicalCandidate[]>; hypotheses: NonNullable<TechnicalOpportunity['fit_hypotheses']> }) {
  const children = childrenByParent.get(component.name) ?? []
  const fits = hypotheses.filter(item => item.component_name === component.name)
  return <li>
    <details open={!component.parent_component}>
      <summary><strong>{component.name}</strong><State value={layerLabel(component.evidence_layer)} /></summary>
      <div className="technical-component-body">
        {component.component_category && <p>{label(component.component_category)}</p>}
        {!!component.source_publication_dates?.length && <p><strong>Source published:</strong> {component.source_publication_dates.join(', ')}</p>}
        {!!component.research_methods?.length && <p><strong>Research method:</strong> {component.research_methods.map(label).join(', ')}</p>}
        {component.material_uncertainties?.map(item => <p className="technical-uncertainty" key={item}>{item}</p>)}
        {fits.map(fit => <article className="technical-fit-hypothesis" key={`${fit.component_name}:${fit.candidate_component_class ?? 'fit'}`}>
          <State value="Possible BTX fit — validation required" />
          <p>{fit.statement}</p>
          {!!fit.candidate_business_units.length && <p><strong>Candidate business unit:</strong> {fit.candidate_business_units.map(item => item.name).join(', ')}</p>}
          {!!fit.candidate_capabilities.length && <p><strong>Candidate capability:</strong> {fit.candidate_capabilities.map(item => item.name).join(', ')}</p>}
          {!!fit.candidate_facilities.length && <p><strong>Candidate facility for capability review:</strong> {fit.candidate_facilities.map(item => item.name).join(', ')}</p>}
        </article>)}
        {!!component.validation_questions?.length && <div><strong>Validate next</strong><ul>{component.validation_questions.map(item => <li key={item}>{item}</li>)}</ul></div>}
      </div>
    </details>
    {!!children.length && <ul>{children.map(child => <Branch key={child.component_id ?? child.name} component={child} childrenByParent={childrenByParent} hypotheses={hypotheses} />)}</ul>}
  </li>
}

export function TechnicalDecompositionSection({ technical, compact = false }: { technical?: TechnicalOpportunity | null; compact?: boolean }) {
  const components = technical?.components ?? []
  const hypotheses = technical?.fit_hypotheses ?? []
  if (!technical || (!components.length && !hypotheses.length)) return compact ? null : <Empty>No supported component breakdown is available for this event. The intelligence remains valid without one.</Empty>
  if (compact) {
    const confirmed = components.filter(item => item.evidence_layer === 'ANNOUNCED_SCOPE').length
    return <p className="technical-fit-summary"><strong>Components and BTX fit:</strong> {components.length} supported system element{components.length === 1 ? '' : 's'} ({confirmed} announced here); {hypotheses.length} possible BTX fit {hypotheses.length === 1 ? 'hypothesis' : 'hypotheses'} requiring validation. Open details to inspect the hierarchy and sources.</p>
  }
  const childrenByParent = new Map<string, TechnicalCandidate[]>()
  for (const component of components) {
    const key = component.parent_component ?? ''
    childrenByParent.set(key, [...(childrenByParent.get(key) ?? []), component])
  }
  const roots = childrenByParent.get('') ?? components.filter(item => !components.some(parent => parent.name === item.parent_component))
  const citations = Array.from(new Map((technical.citations ?? []).map(item => [`${item.url ?? ''}|${item.title}`, item])).values())
  return <section className="technical-decomposition" aria-labelledby="technical-decomposition-heading">
    <div><span className="eyebrow">Evidence-governed research</span><h2 id="technical-decomposition-heading">Components and BTX fit</h2></div>
    <p>{technical.event_summary}</p>
    <div className="technical-layer-key" aria-label="Evidence layer key"><State value="Confirmed in this announcement" /><State value="Supported program architecture" /><State value="Possible BTX fit — validation required" /></div>
    <ul className="technical-component-tree">{roots.map(component => <Branch key={component.component_id ?? component.name} component={component} childrenByParent={childrenByParent} hypotheses={hypotheses} />)}</ul>
    {!!technical.uncertainties.length && <div><strong>What remains unknown</strong><ul>{technical.uncertainties.map(item => <li key={item}>{item}</li>)}</ul></div>}
    {!!citations.length && <div className="technical-citations"><strong>Supporting public sources</strong>{citations.map(item => <EvidenceSource key={`${item.url ?? ''}:${item.title}`} title={item.title} source={item.provenance?.split('|')[0] ?? 'Public source'} date={citationDate(item.provenance)} evidenceState="CITED" url={item.url ?? undefined} detail="High-level public architecture only; no supplier relationship is implied." />)}</div>}
  </section>
}
