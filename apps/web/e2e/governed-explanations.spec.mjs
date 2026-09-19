import { expect, test } from '@playwright/test'
import { openCustomerSection, openRelationshipWorkspace } from './helpers.mjs'

const governedExplanation = {
  provider_status: 'AVAILABLE',
  assisted: true,
  summary: 'This result is explained from its displayed deterministic inputs.',
  key_drivers: ['Controlled taxonomy match'],
  limitations: ['Technical capability alignment does not establish supplier participation or a commercial probability.'],
  what_to_consider: ['Review the displayed supporting evidence before outreach.'],
  evidence_ids: ['fixture-evidence-1'],
  disclosure: 'Explanation assisted by Gemini; underlying result is deterministic.',
}

const relationshipExplanation = {
  ...governedExplanation,
  limitations: ['The path is a possible route and does not establish willingness to make an introduction.'],
}

const technicalBrief = () => ({
  id: 'fixture-technical-brief',
  headline: 'Fixture public contract award',
  what_happened: 'A public award supports increased production.',
  why_it_may_matter: 'Source-backed technical context is available for review.',
  canonical_account_ids: ['lockheed-martin'],
  markets: ['Defense'],
  publication_timestamp: '2026-01-01T00:00:00Z',
  collection_timestamp: '2026-01-01T00:00:00Z',
  freshness: 'CURRENT',
  evidence_ids: ['fixture-evidence-1'],
  source_url: 'https://example.invalid/fixture-award',
  source_system: 'FIXTURE_PUBLIC_SOURCE',
  data_mode: 'SAMPLE',
  resolution_state: 'RESOLVED',
  seller_promotion_state: 'RESOLVED_ELIGIBLE',
  what_to_watch: 'Review the supporting evidence.',
  missing_fields: [],
  seller_summary: 'Fixture seller summary.',
  summary_mode: 'DETERMINISTIC',
  event_timing: 'OBSERVED',
  watchlist_eligible: true,
  priority_reasons: [],
  technical_opportunity: {
    event_summary: 'The public award provides program context for review.',
    product_candidates: [],
    program_candidates: [{ name: 'Fixture Program', basis: 'SOURCE_STATED' }],
    technical_systems: [{ name: 'Actuation system', basis: 'MODEL_INFERRED' }],
    components: [
      { component_id: 'component-round', name: 'Round', basis: 'SOURCE_STATED', evidence_layer: 'ANNOUNCED_SCOPE', confidence_state: 'DIRECTLY_ANNOUNCED', component_category: 'ALL_UP_ROUND', evidence_ids: ['lockheed-javelin'], source_publication_dates: ['2026-08-30'], research_methods: ['REVIEWED_PUBLIC_RELEASE_EXCERPT'], material_uncertainties: ['No BTX participation is established.'], validation_questions: ['Do customer records identify this program?'] },
      { component_id: 'component-missile', name: 'Missile', parent_component: 'Round', basis: 'SOURCE_STATED', evidence_layer: 'SUPPORTED_PROGRAM_ARCHITECTURE', confidence_state: 'SUPPORTED_BY_AUTHORITATIVE_PROGRAM_SOURCE', component_category: 'MISSILE_BODY', evidence_ids: ['army-javelin'], source_publication_dates: ['2023-10-17'], research_methods: ['REVIEWED_PUBLIC_ARTICLE_EXCERPT'], material_uncertainties: ['Supplier and qualification scope are unknown.'], validation_questions: ['Which manufactured hardware is addressable?'] },
    ],
    fit_hypotheses: [{ component_name: 'Missile', evidence_layer: 'BTX_FIT_HYPOTHESIS', fit_state: 'HYPOTHESIS_REQUIRES_VALIDATION', candidate_component_class: 'Structural hardware', candidate_capabilities: [{ id: 'capability-machining', name: 'Precision machining' }], candidate_business_units: [{ id: 'bu-aerospace', name: 'Aerospace' }], candidate_facilities: [], material_uncertainties: ['Program participation is not established.'], validation_questions: ['Validate material, tolerance, certification, and buyer scope.'], evidence_ids: ['army-javelin'], statement: 'Structural hardware is a possible manufacturing-family fit for the missile; program participation, qualification, capacity, and an award are not established.' }],
    citations: [{ evidence_id: 'lockheed-javelin', title: 'Javelin co-production announcement', url: 'https://news.lockheedmartin.com/2026-08-30-Javelin-Joint-Venture-and-Tata-Advanced-Systems-Signs-Agreement-for-Missile-Co-Production-in-India', provenance: 'Lockheed Martin|2026-08-30|REVIEWED_PUBLIC_RELEASE_EXCERPT|partial' }, { evidence_id: 'army-javelin', title: 'U.S. Army Javelin system overview', url: 'https://www.army.mil/article/270870/through_lockheed_and_raytheon_collaboration_the_west_point_museum_unveils_javelin_exhibit', provenance: 'U.S. Army|2023-10-17|REVIEWED_PUBLIC_ARTICLE_EXCERPT|partial' }],
    uncertainties: ['The system and component candidate are model-inferred technical hypotheses.'],
    provider_status: 'AVAILABLE',
    language_provider: 'gemini',
    language_model: 'fixture-model',
    matches: [{ candidate_name: 'Actuator housing', basis: 'MODEL_INFERRED', status: 'MATCHED', component_name: 'Actuator housing', business_units: [{ name: 'Aerospace' }] }],
    disclosure: 'Technical decomposition is Gemini-assisted. BTX component, capability and Business Unit matching is deterministic.',
    governed_explanation: governedExplanation,
  },
})

async function addRelationshipExplanationFixture(page) {
  await page.route('**/api/accounts/lockheed-martin/relationships?depth=2', async route => {
    const response = await route.fetch()
    const payload = await response.json()
    for (const collection of [payload.seller_direct_relationships, payload.seller_paths, payload.seller_projection?.validated, payload.seller_projection?.needs_validation]) {
      for (const path of collection ?? []) path.governed_explanation = relationshipExplanation
    }
    await route.fulfill({ response, json: payload })
  })
}

async function addTodayTechnicalExplanationFixture(page) {
  await page.route('**/api/today', async route => {
    const response = await route.fetch()
    const payload = await response.json()
    payload.command_center.current_signal_briefs = [technicalBrief()]
    await route.fulfill({ response, json: payload })
  })
}

async function openLockheed(page) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Customers & Prospects' }).click()
  await page.getByPlaceholder('Search Customer, industry, or location').fill('Lockheed')
  await page.getByRole('link', { name: 'Lockheed Martin', exact: true }).click()
  await expect(page.locator('.account-workspace')).toBeVisible()
}

async function openLockheedMobile(page) {
  await page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button', { name: 'Customers & Prospects' }).click()
  await page.getByPlaceholder('Search Customer, industry, or location').fill('Lockheed')
  await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: 'Lockheed Martin', exact: true }).click()
  await expect(page.locator('.account-workspace')).toBeVisible()
}

test('Signal Brief Technical Fit retains deterministic context while disclosing its governed explanation', async ({ page }, testInfo) => {
  await addTodayTechnicalExplanationFixture(page)
  await page.goto('/')
  await page.getByRole('button', { name: 'Market watch and source coverage' }).click()
  const brief = page.locator('.seller-signal-brief').filter({ hasText: 'Fixture public contract award' })
  await expect(brief).toBeVisible()
  await brief.getByRole('button', { name: 'View supporting evidence (1)' }).click()
  await brief.getByRole('button', { name: 'Program, components and possible BTX fit' }).click()
  await expect(brief).toContainText('Source stated')
  await expect(brief).toContainText('Model inferred')
  await expect(brief).toContainText('Controlled BTX match: Actuator housing')
  await expect(brief).toContainText('Applicable BU: Aerospace')
  await expect(brief).toContainText('Confirmed in this announcement')
  await expect(brief).toContainText('Supported program architecture')
  await expect(brief).toContainText('Possible BTX fit — validation required')
  await expect(brief).toContainText('program participation, qualification, capacity, and an award are not established')
  const explanation = brief.getByRole('button', { name: 'Why this technical fit may matter' })
  await explanation.click()
  await expect(brief).toContainText('Technical capability alignment does not establish supplier participation')
  await expect(brief).not.toContainText(/BTX currently supplies|win probability|likely supplier|will win/i)
  await brief.screenshot({ path: testInfo.outputPath('technical-fit-desktop.png') })
})

test('Technical Fit disclosure remains contained at 390px and 320px', async ({ page }, testInfo) => {
  await addTodayTechnicalExplanationFixture(page)
  for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 700 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await page.getByRole('button', { name: 'Market watch and source coverage' }).click()
    const brief = page.locator('.seller-signal-brief').filter({ hasText: 'Fixture public contract award' })
    await brief.getByRole('button', { name: 'View supporting evidence (1)' }).click()
    await brief.getByRole('button', { name: 'Program, components and possible BTX fit' }).click()
    await brief.getByRole('button', { name: 'Why this technical fit may matter' }).click()
    await expect(brief).toContainText('Controlled BTX match: Actuator housing')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    await brief.screenshot({ path: testInfo.outputPath(`technical-fit-${viewport.width}.png`) })
  }
})

test('Relationship reference retains its governed path and evidence beside the canonical graph', async ({ page }) => {
  await addRelationshipExplanationFixture(page)
  await page.goto('/')
  await openLockheed(page)
  const relationshipPanel = page.locator('.account-workspace-relationship')
  await openCustomerSection(page, /People and relationship paths/)
  const detail = relationshipPanel.locator('.seller-relationship-card').first()
  await expect(detail).toContainText('Connection:')
  await openRelationshipWorkspace(page)
  await expect(relationshipPanel.locator('.relationship-graph-canvas')).toHaveCount(0)
  await expect(detail.getByRole('button', { name: /Evidence/ })).toBeVisible()
  await detail.getByRole('button', { name: 'Why this relationship path may be useful' }).click()
  await expect(detail).toContainText('Controlled taxonomy match')
  await expect(detail).not.toContainText(/warm introduction|strength score|probability/i)
})

test('Relationship explanation remains contained at 390px and 320px', async ({ page }) => {
  await addRelationshipExplanationFixture(page)
  for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 700 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await openLockheedMobile(page)
    const relationshipPanel = page.locator('.account-workspace-relationship')
    await openCustomerSection(page, /People and relationship paths/)
    const detail = relationshipPanel.locator('.seller-relationship-card').first()
    await detail.getByRole('button', { name: 'Why this relationship path may be useful' }).click()
    await expect(detail).toContainText('This result is explained from its displayed deterministic inputs.')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
})
