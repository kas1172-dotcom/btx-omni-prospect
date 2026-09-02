import { expect, test } from '@playwright/test'

const governedExplanation = {
  provider_status: 'AVAILABLE',
  assisted: true,
  summary: 'The governed result is explained from its displayed deterministic inputs.',
  key_drivers: ['Controlled taxonomy match'],
  limitations: ['Technical capability alignment does not establish supplier participation or a commercial probability.'],
  what_to_consider: ['Review the displayed governed evidence before outreach.'],
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
  why_it_may_matter: 'Governed public technical context is available for review.',
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
  what_to_watch: 'Review governed evidence.',
  missing_fields: [],
  seller_summary: 'Fixture seller summary.',
  summary_mode: 'DETERMINISTIC',
  event_timing: 'OBSERVED',
  watchlist_eligible: true,
  priority_reasons: [],
  technical_opportunity: {
    event_summary: 'Public award supports a governed program context.',
    product_candidates: [],
    program_candidates: [{ name: 'Fixture Program', basis: 'SOURCE_STATED' }],
    technical_systems: [{ name: 'Actuation system', basis: 'MODEL_INFERRED' }],
    uncertainties: ['The system and component candidate are model-inferred technical hypotheses.'],
    provider_status: 'AVAILABLE',
    language_provider: 'gemini',
    language_model: 'fixture-model',
    matches: [{ candidate_name: 'Actuator housing', basis: 'MODEL_INFERRED', status: 'MATCHED', component_name: 'Actuator housing', business_units: [{ name: 'Aerospace' }] }],
    disclosure: 'Technical decomposition is Gemini-assisted. BTX component, capability and Business Unit matching is deterministic.',
    governed_explanation: governedExplanation,
  },
})

async function addTechnicalExplanationFixture(page) {
  await page.route('**/api/monitor/health', async route => {
    const response = await route.fetch()
    const payload = await response.json()
    payload.signal_briefs = [technicalBrief()]
    await route.fulfill({ response, json: payload })
  })
}

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
  await page.locator('.account-row').filter({ hasText: 'Lockheed' }).first().click()
  await expect(page.locator('.account-workspace')).toBeVisible()
}

async function openLockheedMobile(page) {
  await page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button', { name: 'Customers & Prospects' }).click()
  await page.getByPlaceholder('Search Customer, industry, or location').fill('Lockheed')
  await page.locator('.portfolio-mobile-list .ui-mobile-row').filter({ hasText: 'Lockheed' }).first().click()
  await expect(page.locator('.account-workspace')).toBeVisible()
}

test('Signal Brief Technical Fit retains deterministic context while disclosing its governed explanation', async ({ page }) => {
  await addTechnicalExplanationFixture(page)
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Monitor' }).click()
  const brief = page.locator('.seller-signal-brief').filter({ hasText: 'Fixture public contract award' })
  await expect(brief).toBeVisible()
  await brief.getByRole('button', { name: 'Potential BTX Technical Fit' }).click()
  await expect(brief).toContainText('Source stated')
  await expect(brief).toContainText('Model inferred')
  await expect(brief).toContainText('Controlled BTX match: Actuator housing')
  await expect(brief).toContainText('Applicable BU: Aerospace')
  const explanation = brief.getByRole('button', { name: 'Why this technical fit may matter' })
  await explanation.click()
  await expect(brief).toContainText('Technical capability alignment does not establish supplier participation')
  await expect(brief).not.toContainText(/BTX currently supplies|win probability|likely supplier|will win/i)
})

test('Technical Fit disclosure remains contained at 390px and 320px', async ({ page }) => {
  await addTodayTechnicalExplanationFixture(page)
  for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 700 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/')
    const brief = page.locator('.seller-signal-brief').filter({ hasText: 'Fixture public contract award' })
    await brief.getByRole('button', { name: 'Potential BTX Technical Fit' }).click()
    await brief.getByRole('button', { name: 'Why this technical fit may matter' }).click()
    await expect(brief).toContainText('Controlled BTX match: Actuator housing')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
})

test('Relationship graph retains its governed path and evidence while disclosing its explanation', async ({ page }) => {
  await addRelationshipExplanationFixture(page)
  await page.goto('/')
  await openLockheed(page)
  const relationshipPanel = page.locator('.account-workspace-relationship')
  await relationshipPanel.getByRole('tab', { name: 'Graph view' }).click()
  await relationshipPanel.locator('.relationship-graph-node').first().click()
  const detail = relationshipPanel.locator('.relationship-graph-detail')
  await expect(detail).toContainText('Selected context')
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
    await relationshipPanel.getByRole('button', { name: /Relationship Intelligence/ }).click()
    await relationshipPanel.getByRole('tab', { name: 'Graph view' }).click()
    await relationshipPanel.locator('.relationship-graph-node').first().click()
    const detail = relationshipPanel.locator('.relationship-graph-detail')
    await detail.getByRole('button', { name: 'Why this relationship path may be useful' }).click()
    await expect(detail).toContainText('The governed result is explained from its displayed deterministic inputs.')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  }
})
