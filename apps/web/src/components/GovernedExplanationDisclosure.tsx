import type { GovernedExplanation } from '../types/api'
import { Disclosure } from './UI'

export function GovernedExplanationDisclosure({ title, explanation }: { title: string; explanation?: GovernedExplanation | null }) {
  if (!explanation) return null
  return <Disclosure title={title}><div className="detail-stack governed-explanation"><p>{explanation.summary}</p>{explanation.key_drivers.length > 0 && <section><strong>Key drivers</strong><ul>{explanation.key_drivers.map(item => <li key={item}>{item}</li>)}</ul></section>}{explanation.limitations.length > 0 && <section><strong>Limitations / missing context</strong><ul>{explanation.limitations.map(item => <li key={item}>{item}</li>)}</ul></section>}{explanation.what_to_consider.length > 0 && <section><strong>What to consider</strong><ul>{explanation.what_to_consider.map(item => <li key={item}>{item}</li>)}</ul></section>}<small>{explanation.assisted ? explanation.disclosure : 'Explanation based on the displayed result and its supporting evidence.'}</small></div></Disclosure>
}
