// Explicit development/test illustrations. Dynamically imported only inside import.meta.env.DEV.
import type { Opportunity } from '../../types/opportunities'

const examples = [
  ['honeywell', 'Honeywell', 'Structural brackets', 'Commercial Aerospace', 'Proposal', 120000000, 82, null, 'YES', 'YES', 'Chandler'],
  ['northrop', 'Northrop Grumman', 'Guidance sensor mounts', 'Defense', 'Discovery', 98000000, 76, null, 'YES', 'YES', 'ERA'],
  ['raytheon', 'Raytheon', 'Precision housings', 'Defense', 'Qualification', 64000000, 68, null, 'YES', 'UNKNOWN', 'Chandler'],
  ['applied', 'Applied Materials', 'Vacuum chamber components', 'Semiconductor', 'Discovery', 40000000, 61, null, 'UNKNOWN', 'YES', 'ERA'],
  ['lockheed', 'Lockheed Martin', 'Sensor mounts', 'Defense', 'Qualification', 26000000, 41, null, 'NO', 'NO', 'Chandler'],
  ['boeing', 'Boeing', 'Machined valve bodies', 'Commercial Aerospace', 'Discovery', 36000000, null, [45, 75], 'UNKNOWN', 'UNKNOWN', null],
  ['medtronic', 'Medtronic', 'Surgical instrument housings', 'Medical Device', 'Discovery', null, null, [50, 72], 'YES', 'UNKNOWN', 'ERA'],
  ['kratos', 'Kratos TDI', 'Turbine component machining', 'Defense', 'Discovery', 42000000, null, [42, 78], 'UNKNOWN', 'YES', 'Chandler'],
  ['spacex', 'SpaceX', 'Flight hardware assemblies', 'Space', 'Qualification', 30000000, 79, null, 'YES', 'YES', 'ERA'],
  ['rocket', 'Rocket Lab', 'Precision propulsion components', 'Space', 'Discovery', 36000000, null, [35, 70], 'UNKNOWN', 'UNKNOWN', null],
  ['intuitive', 'Intuitive Surgical', 'Instrument housings', 'Medical Device', 'Discovery', null, null, [40, 80], 'UNKNOWN', 'UNKNOWN', 'ERA'],
  ['boston', 'Boston Dynamics', 'Actuator components', null, 'Discovery', 18000000, null, [20, 60], 'NO', 'UNKNOWN', null],
] as const

export const opportunityFixture: Opportunity[] = examples.map(([id, company, title, market, stage, value, score, range, qualified, durable, bu], index) => {
  // Authored examples, not a frontend scoring implementation.
  const factorExamples: Record<string, Array<[number | null, number | null]>> = {
    honeywell: [[90, 27], [80, 20], [80, 12], [70, 7], [80, 8], [80, 8]],
    northrop: [[80, 24], [80, 20], [80, 12], [60, 6], [70, 7], [70, 7]],
    raytheon: [[70, 21], [70, 17.5], [70, 10.5], [60, 6], [60, 6], [70, 7]],
    applied: [[60, 18], [60, 15], [60, 9], [60, 6], [60, 6], [70, 7]],
    lockheed: [[40, 12], [40, 10], [40, 6], [40, 4], [40, 4], [50, 5]],
    spacex: [[80, 24], [90, 22.5], [70, 10.5], [70, 7], [80, 8], [70, 7]],
    boeing: [[null, null], [60, 15], [60, 9], [70, 7], [70, 7], [70, 7]],
  }
  const missing = range ? (id === 'boeing' ? ['program_durability'] : ['program_durability', 'btx_manufacturing_fit']) : []
  const decision: Opportunity['opportunity_priority'] = {
    decision_id: `illustrative-${id}`, family: 'OPPORTUNITY_PRIORITY', subject_id: `dev-${id}`, as_of: '2026-09-20', revision: 'dev-illustration-only',
    configuration_version: 'BTX_SCORING_RUBRIC_V2', score, status: range ? 'INCOMPLETE' : 'COMPLETE',
    ...(range ? { score_range: { low: range[0], high: range[1] } } : {}),
    interpretation: 'Illustrative development fixture; not a scored customer record.', eligibility_reasons: [], blocking_constraints: [],
    data_coverage: { present: range ? (id === 'boeing' ? 5 : 4) : 6, applicable: 6, ratio: range ? (id === 'boeing' ? 0.70 : 0.45) : 1, missing_fields: missing },
    factors: [
      ['program_durability', 30], ['btx_manufacturing_fit', 25], ['addressable_btx_work', 15],
      ['program_momentum', 10], ['strategic_target_fit', 10], ['btx_commercial_adjacency', 10],
    ].map(([key, weight], factorIndex) => {
      const [points, contribution] = (factorExamples[id] ?? [[null, null], [null, null], [60, 9], [70, 7], [70, 7], [70, 7]])[factorIndex]
      return { key: String(key), weight: Number(weight), points, contribution, reason: points != null ? 'Illustrative evidence for layout verification.' : 'Factor-level evidence not supplied in this illustration.', evidence_ids: [], required_fields: [], observed_fields: [] }
    }),
  }
  const unavailable = { ...decision, score: null, score_range: undefined, status: 'INELIGIBLE', factors: [], eligibility_reasons: ['Not evaluated in the development fixture.'] }
  return {
    opportunity_id: `dev-${id}`, component_id: `dev-component-${id}`, account_id: `dev-account-${id}`, account_name: company,
    lane: index < 7 ? 'CUSTOMER_EXPANSION' : 'PROSPECT', title, market, bu, stage: stage.toUpperCase(), value_minor: value, currency: 'USD',
    qualification_status: qualified, durability_status: durable, opportunity_priority: decision, pwin: { ...unavailable, family: 'PWIN' }, delivery_feasibility: { ...unavailable, family: 'DELIVERY_FEASIBILITY' },
    gates: { qualified_and_durable: qualified === 'YES' && durable === 'YES', durable_best_bet: id === 'honeywell' || id === 'spacex', qualification_checks: { scoped_requirement: qualified === 'UNKNOWN' ? null : qualified === 'YES' }, durability_checks: { recurring_program: durable === 'UNKNOWN' ? null : durable === 'YES' }, evidence_ids: [] },
    next_action: 'Validate the scoped requirement and request supporting evidence.', business_context: 'Illustrative development pursuit. These values do not describe an actual customer opportunity.', material_uncertainties: range ? ['Confirm missing scoring inputs before prioritizing this pursuit.'] : [],
    source_record_id: `dev-${id}`, as_of: '2026-09-20', revision: 'dev-illustration-only',
    attractiveness: { score: null, score_range: { low: 0, high: 100 }, coverage: 0, configuration_version: 'not-used', missingness: [], subject_id: `dev-${id}` },
  }
})
