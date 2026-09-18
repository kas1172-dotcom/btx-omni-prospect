import { expect, test } from '@playwright/test'

async function openOrganization(page, id, name) {
  await page.goto(`/#/accounts/${id}`)
  await expect(page.getByRole('heading', { name, level: 1 })).toBeVisible()
}

test('organization mode adapts without treating research or CRM presence as a customer relationship', async ({ page }) => {
  await openOrganization(page, 'lockheed-martin', 'Lockheed Martin')
  await expect(page.locator('.account-workspace').getByText(/Customer 360/i).first()).toBeVisible()
  await expect(page.getByText('Confirmed BTX customer').first()).toBeVisible()
  await expect(page.getByText('Expansion pursuit', { exact: true })).toHaveCount(0)

  await openOrganization(page, 'intel', 'Intel')
  await expect(page.locator('.account-workspace').getByText(/Prospect 360/i).first()).toBeVisible()
  await expect(page.getByText('No confirmed BTX commercial relationship').first()).toBeVisible()
  await page.getByRole('button', { name: /Related BTX activity to review/ }).click()
  await expect(page.getByText('No confirmed BTX commercial history is available for this Prospect.')).toBeVisible()

  await openOrganization(page, 'rtx-collins-aerospace', 'RTX (Raytheon Technologies) / Collins Aerospace')
  await expect(page.getByText('Relationship needs review', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/commercial records exist, but the governed organization classification does not confirm/i)).toBeHidden()
  const why = page.getByRole('button', { name: 'Why this?' }).first()
  await why.click()
  await expect(page.getByText(/commercial records exist, but the governed organization classification does not confirm/i)).toBeVisible()
})

test('evidence is closed by default, targeted reasoning opens independently, and mobile uses a drawer', async ({ page }) => {
  await openOrganization(page, 'lockheed-martin', 'Lockheed Martin')
  const evidence = page.locator('.account-workspace > .supporting-evidence > .supporting-evidence-trigger')
  await expect(evidence).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('heading', { name: 'How this was determined' })).toHaveCount(0)
  await evidence.click()
  await expect(evidence).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('heading', { name: 'How this was determined' })).toBeVisible()
  await evidence.click()
  await expect(evidence).toHaveAttribute('aria-expanded', 'false')

  await page.setViewportSize({ width: 390, height: 844 })
  await openOrganization(page, 'intel', 'Intel')
  const mobileEvidence = page.locator('.account-workspace > .supporting-evidence > .supporting-evidence-trigger')
  await mobileEvidence.click()
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'Supporting evidence' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})

test('customer expansion pursuit reuses one assessment and ranked internal records', async ({ page }) => {
  const eventId = 'expansion-event'
  const assessmentId = 'assessment-expansion'
  const accountResponse = await page.request.get('/api/accounts/lockheed-martin')
  const account = await accountResponse.json()
  const briefing = {
    id: eventId,
    context_id: `${eventId}:lockheed-martin`,
    assessment_id: assessmentId,
    assessment_version: 7,
    canonical_account_ids: ['lockheed-martin'],
    canonical_program_id: 'program-expansion',
    headline: 'Reviewed program expansion signal',
    seller_summary: 'A reviewed signal may warrant a scoped expansion review.',
    what_happened: 'A source-backed program change was announced.',
    why_it_may_matter: 'Existing account history may help BTX validate adjacent work without establishing program participation.',
    what_to_watch: 'Confirm program, component, facility and buyer scope.',
    recommended_action: 'Review the cited program notice and the related quote before proposing pursuit work.',
    action_rationale: 'The account relationship is established; participation in the new program is not.',
    material_uncertainties: ['BTX participation in the announced program is not established.'],
    markets: ['Defense'],
    event_timing: 'RECENT',
    freshness: 'CURRENT',
    data_mode: 'LIVE_PUBLIC',
    analysis_status: 'READY',
    commercial_relevance_state: 'REVIEW_REQUIRED',
    priority_eligible: false,
    summary_mode: 'DETERMINISTIC',
    publication_timestamp: '2026-09-01T00:00:00Z',
    source_system: 'Official program source',
    source_url: 'https://example.com/program',
    resolution_state: 'RESOLVED_ELIGIBLE',
    seller_promotion_state: 'ELIGIBLE',
    evidence_ids: ['public-program-source'],
    references: [{ evidence_id: 'public-program-source', title: 'Official program source', url: 'https://example.com/program', publication_date: '2026-09-01' }],
    priority_reasons: [],
    missing_fields: [],
    evidence_package: { commercial_record_scope: 'EXACT_PROGRAM', commercial_records: [{ collection: 'quotes', record_id: 'quote-expansion', date: '2026-08-15', display_name: 'Expansion component quote', match_reasons: ['Shares the governed program scope'], match_strength: 'Strong scoped match', unknowns: 'Technical qualification remains unconfirmed.', validation_action: 'Inspect the quote and confirm program scope.', status: 'OPEN', value_minor: 1250000, currency: 'USD' }] },
  }
  account.organization_360.expansion_pursuit = { assessment_id: assessmentId, assessment_version: 7, event_id: eventId, headline: briefing.headline, program_id: briefing.canonical_program_id, governed_action: briefing.recommended_action }
  account.customer_360.intelligence = [{ id: eventId, business_briefing: briefing }, ...account.customer_360.intelligence]
  await page.route('**/api/accounts/lockheed-martin', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(account) }))
  await page.route('**/api/accounts/lockheed-martin/commercial/quotes?record_id=quote-expansion&limit=1', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ account_id: 'lockheed-martin', revision: 'fixture', records: [{ quote_id: 'quote-expansion', title: 'Expansion component quote', status: 'OPEN', value_minor: 1250000, currency: 'USD' }] }) }))

  await openOrganization(page, 'lockheed-martin', 'Lockheed Martin')
  await expect(page.getByText('Expansion pursuit', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: /Current intelligence assessment/ }).click()
  await expect(page.getByRole('heading', { name: briefing.headline }).first()).toBeVisible()
  await expect(page.getByText('Why it may matter:')).toBeVisible()
  await page.locator('.organization-briefing').getByRole('button', { name: /View supporting evidence/ }).click()
  await page.getByRole('button', { name: 'Inspect source record' }).first().click()
  await expect(page.getByRole('region', { name: 'Expansion component quote source record' })).toContainText('Expansion component quote')
  await page.getByRole('button', { name: 'Use in Omni' }).first().click()
  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByRole('dialog', { name: 'Ask Omni' })).toContainText('Lockheed Martin')
})
