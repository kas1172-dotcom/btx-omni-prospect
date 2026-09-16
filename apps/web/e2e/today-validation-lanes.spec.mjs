import { expect, test } from '@playwright/test'

const score = {
  score: 84.71,
  factors: [{ key: 'source_quality', points: 95, reason: 'Official announcement retained.', evidence_ids: ['lockheed-javelin'] }],
  data_coverage: { present: 4, applicable: 5 },
  decision_id: 'signal-confidence-javelin',
  configuration_version: 'SIGNAL_CONFIDENCE_1',
  input_configuration_version: 'ASSESSMENT_INPUT_4',
}

const brief = (overrides = {}) => ({
  id: 'event-javelin',
  context_id: 'event-javelin|lockheed-martin|ALL_BUSINESS_UNITS',
  assessment_id: 'a'.repeat(64),
  assessment_version: 4,
  headline: 'Lockheed Martin and Tata announce Javelin co-production agreement',
  what_happened: 'Lockheed Martin and Tata announced a Javelin co-production agreement in India.',
  why_it_may_matter: 'Existing Lockheed context makes this worth validating, but BTX relevance is not established.',
  canonical_account_ids: ['lockheed-martin'],
  canonical_program_id: null,
  markets: ['Defense'],
  publication_timestamp: '2026-08-30T10:00:00Z',
  collection_timestamp: '2026-09-15T10:00:00Z',
  freshness: 'STALE',
  evidence_ids: ['lockheed-javelin'],
  source_url: 'https://news.lockheedmartin.com/2026-08-30-Javelin',
  source_system: 'Lockheed Martin',
  data_mode: 'LIVE_PUBLIC',
  resolution_state: 'RESOLVED',
  seller_promotion_state: 'RESOLVED_NEEDS_REVIEW',
  what_to_watch: 'Whether internal records establish Javelin, Troy, Tucson, or relevant buyer activity.',
  recommended_action: 'Verify internal Lockheed and RTX records for Javelin, Troy, Tucson, missile-component, or relevant buyer activity.',
  missing_fields: [],
  seller_summary: 'The announcement is verified; possible BTX relevance requires internal validation.',
  summary_mode: 'DETERMINISTIC',
  event_timing: 'OBSERVED',
  watchlist_eligible: true,
  priority_reasons: [],
  analysis_status: 'READY',
  commercial_relevance_state: 'ESTABLISHED_ACCOUNT_REVIEW',
  priority_eligible: false,
  action_rationale: 'Validate governed internal history before treating this as an opportunity.',
  material_uncertainties: ['No BTX participation in Javelin is established.'],
  references: [{ evidence_id: 'lockheed-javelin', title: 'Javelin co-production announcement', url: 'https://news.lockheedmartin.com/2026-08-30-Javelin', publication_date: '2026-08-30' }],
  signal_confidence: score,
  technical_opportunity: {
    event_summary: 'The announcement and authoritative program sources support a bounded system hierarchy.',
    product_candidates: [], program_candidates: [], technical_systems: [], matches: [],
    components: [{ component_id: 'round', name: 'Round', basis: 'SOURCE_STATED', evidence_layer: 'ANNOUNCED_SCOPE', evidence_ids: ['lockheed-javelin'], source_publication_dates: ['2026-08-30'], material_uncertainties: [], validation_questions: ['Do internal records identify this program?'] }],
    fit_hypotheses: Array.from({ length: 8 }, (_, index) => ({ component_name: 'Round', evidence_layer: 'BTX_FIT_HYPOTHESIS', fit_state: 'HYPOTHESIS_REQUIRES_VALIDATION', candidate_component_class: `Candidate ${index + 1}`, candidate_capabilities: [], candidate_business_units: [{ id: 'BU-GENELMEC', name: 'General Mechanical' }], candidate_facilities: [], material_uncertainties: ['Participation is not established.'], validation_questions: ['Validate scope.'], evidence_ids: ['lockheed-javelin'], statement: `Candidate fit ${index + 1} requires validation.` })),
    citations: [{ evidence_id: 'lockheed-javelin', title: 'Javelin co-production announcement', url: 'https://news.lockheedmartin.com/2026-08-30-Javelin', publication_date: '2026-08-30', publisher: 'Lockheed Martin' }],
    uncertainties: ['No BTX participation is established.'], provider_status: 'AVAILABLE', disclosure: 'Possible fit requires validation.',
  },
  ...overrides,
})

const item = (signal, outcome_lane) => ({
  id: signal.context_id,
  event_id: signal.id,
  kind: 'PUBLIC_SIGNAL',
  outcome_lane,
  account_id: signal.canonical_account_ids[0],
  reason: signal.why_it_may_matter,
  recommended_action: signal.recommended_action,
  evidence_ids: signal.evidence_ids,
  observed_at: signal.publication_timestamp,
  data_mode: signal.data_mode,
  lifecycle_state: signal.freshness === 'CURRENT' ? 'CURRENT' : 'SAVED_RECENT',
  business_unit_ids: ['BU-GENELMEC'],
  signal_brief: signal,
})

for (const width of [390, 1440]) {
  test(`Today keeps action and validation outcomes distinct at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    const validationBrief = brief()
    const actionBrief = brief({
      id: 'event-honeywell-action', context_id: 'event-honeywell-action|honeywell|ALL_BUSINESS_UNITS', assessment_id: 'b'.repeat(64), assessment_version: 2,
      canonical_account_ids: ['honeywell'], headline: 'Honeywell expansion supports a governed customer action', seller_promotion_state: 'RESOLVED_ELIGIBLE', freshness: 'CURRENT',
      commercial_relevance_state: 'ESTABLISHED_COMMERCIAL_RELEVANCE', priority_eligible: true, signal_confidence: { ...score, score: 91.2 }, technical_opportunity: undefined,
    })
    const validationItem = item(validationBrief, 'NEEDS_VALIDATION')
    const actionItem = item(actionBrief, 'ACTION_PRIORITIES')
    await page.route('**/api/today', async route => {
      const response = await route.fetch()
      const payload = await response.json()
      const internal = payload.command_center.priority_briefing.filter(row => row.kind === 'COMMERCIAL_REVIEW')
      payload.command_center.priority_briefing = [...internal, actionItem]
      payload.command_center.action_priorities = [actionItem]
      payload.command_center.needs_validation_assessments = [validationItem]
      payload.command_center.public_intelligence_counts = { action_priorities: 1, needs_validation: 1 }
      await route.fulfill({ response, json: payload })
    })
    let omniRequest
    await page.route('**/api/omni', async route => {
      omniRequest = route.request().postDataJSON()
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ content: 'The Javelin announcement is verified. Potential BTX relevance requires internal validation.', account_id: 'lockheed-martin', account_name: 'Lockheed Martin', citations: ['lockheed-javelin'], citation_links: [{ label: 'Lockheed Martin', url: validationBrief.source_url }], provenance: ['STORED_INTELLIGENCE'], missingness: validationBrief.material_uncertainties, recommended_action: validationBrief.recommended_action, context_used: { assessment_id: validationBrief.assessment_id, assessment_version: 4 }, provider_status: 'AVAILABLE', language_provider: 'deterministic' }) })
    })

    await page.goto('/#/today')
    await page.getByRole('button', { name: 'Public intelligence', exact: true }).click()
    await expect(page.locator('.today-lane-summary')).toHaveText('1 action priority · 1 needs validation')
    await expect(page.locator('[data-priority-id]')).toHaveCount(1)
    await expect(page.locator('[data-validation-id]')).toHaveCount(1)
    await page.getByLabel('Filter priorities by customer or prospect').selectOption('lockheed-martin')
    await expect(page.locator('.today-lane-summary')).toHaveText('0 action priorities · 1 needs validation')
    await expect(page.locator('[data-priority-id]')).toHaveCount(0)
    const review = page.locator('[data-validation-id]')
    await expect(review).toContainText('Lockheed Martin')
    await expect(review).toContainText('Signal Confidence 84.71/100')
    await expect(review).toContainText('Potential BTX relevance not yet established')
    await expect(review).toContainText(validationBrief.recommended_action)
    await expect(review).toContainText('Aug 30, 2026')
    await review.getByRole('button', { name: 'Evidence, component hierarchy, and uncertainty' }).click()
    await expect(review).toContainText('8 possible BTX fit hypotheses requiring validation')
    await review.getByRole('button', { name: 'Use in Omni', exact: true }).click()
    await page.getByLabel('Open Omni assistant').click()
    await page.locator('#omni-message').fill('Explain this selected assessment.')
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    await expect.poll(() => omniRequest?.context?.selected_assessment).toEqual({ assessment_id: validationBrief.assessment_id, assessment_version: 4, event_id: validationBrief.id, account_id: 'lockheed-martin' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
    await page.getByLabel('Close Omni').click()
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
    await page.screenshot({ path: testInfo.outputPath(`today-needs-validation-${width}.png`) })
  })
}
