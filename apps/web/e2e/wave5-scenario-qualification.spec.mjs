import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const evidenceDir = process.env.BTX_WAVE5_EVIDENCE_DIR
const screenshot = async (page, testInfo, name) => {
  const directory = evidenceDir ?? testInfo.outputDir
  mkdirSync(directory, { recursive: true })
  await page.screenshot({ path: join(directory, name), fullPage: true })
}

test('journeys 1–5 remain explicitly incomplete without manufactured evidence', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const federal = await (await page.request.get('/api/federal-procurement')).json()
  const opportunity = federal.active.opportunities.find(item => item.opportunity_id === 'SAM-1')
  expect(opportunity.data_mode).toBe('SAMPLE')
  expect(federal.sam.coverage_complete).toBe(false)
  expect(opportunity.assessment.durability.state).toBe('ONE_TIME_OR_UNKNOWN')
  expect(opportunity.assessment.durability.historical_award_count).toBe(0)
  expect(opportunity.assessment.routes.some(route => route.route_type === 'STRATEGIC_PARTNER')).toBe(false)
  expect(opportunity.assessment.stage.explanation).toContain('not an open bid')

  const planning = await (await page.request.get('/api/planning')).json()
  expect(planning.strategic_partnerships).toEqual([])

  const intelligence = await (await page.request.get('/api/intelligence')).json()
  const curated = Object.fromEntries(
    intelligence.signals
      .filter(signal => ['boeing', 'lockheed-martin', 'intel'].includes(signal.account_id))
      .map(signal => [signal.account_id, signal]),
  )
  expect(curated.boeing.source_url).toMatch(/^https:\/\/www\.faa\.gov\//)
  expect(curated['lockheed-martin'].source_url).toMatch(/^https:\/\/www\.nasa\.gov\//)
  expect(curated.intel.source_validation_state).toBe('AUTOMATION_BLOCKED')
  for (const signal of Object.values(curated)) {
    expect(signal.data_mode).toBe('CURATED_PUBLIC')
    expect(signal.business_briefing).toBeUndefined()
  }

  const accounts = await (await page.request.get('/api/accounts')).json()
  const intel = accounts.accounts.find(account => account.id === 'intel')
  const huxwrx = accounts.accounts.find(account => account.id === 'huxwrx')
  expect(intel.relationship).toBe('PUBLIC_MARKET')
  expect(intel.commercial_context_state).toBe('UNAVAILABLE')
  expect(huxwrx.relationship).toBe('CURRENT_CUSTOMER')
  expect(huxwrx.commercial_context_state).toBe('SAMPLE')

  await page.goto('/#/intelligence/federal')
  await page.getByRole('button', { name: 'Aerospace precision component sources sought' }).click()
  await expect(page.getByText('Durability not yet established')).toBeVisible()
  await expect(page.getByText(/not an open bid/i).first()).toBeVisible()
  await screenshot(page, testInfo, 'journeys-1-3-federal-incomplete-1440x900.png')

  await page.goto('/#/intelligence')
  await page.getByRole('searchbox', { name: 'Search Intelligence' }).fill('Boeing')
  const card = page.locator('.intelligence-card').filter({ hasText: 'FAA production oversight update' })
  await expect(card).toBeVisible()
  await expect(card).toContainText('Analysis in progress')
  await expect(card).toContainText('The commercial implication has not yet been established.')
  await screenshot(page, testInfo, 'journeys-4-5-public-assessment-incomplete-1440x900.png')
})

test('journey 6 keeps the internal-risk identity, evidence and action across surfaces', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  const today = await (await page.request.get('/api/today')).json()
  const alert = today.commercial_alerts.find(item => item.id === 'alert-bookings_decline-lockheed-martin-high-tech-solutions')
  expect(alert).toMatchObject({
    account_id: 'lockheed-martin',
    trigger_reason: 'Bookings declined versus prior period',
    recommended_action: 'Review lost demand and recovery plan.',
    evidence_ids: ['commercial:lockheed-martin:BU-HTS'],
  })
  const actions = await (await page.request.get('/api/actions')).json()
  const suggestion = actions.suggestions.find(item => item.source_alert_id === alert.id)
  expect(suggestion.account_id).toBe(alert.account_id)
  expect(suggestion.evidence_ids).toEqual(alert.evidence_ids)

  await page.goto('/#/today')
  await page.getByLabel('Search Today work').fill('Bookings declined')
  const row = page.locator(`[data-priority-id="${alert.id}"]`)
  await expect(row).toHaveCount(1)
  await row.getByRole('button', { name: 'Evidence and governed action' }).click()
  await expect(row).toContainText(alert.evidence_ids[0])
  await expect(row).toContainText(alert.recommended_action)
  await screenshot(page, testInfo, 'journey-6-internal-risk-1440x900.png')

  await row.locator('.today-customer-link').click()
  await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Organization decision summary' })).toContainText('Governed next action')
})

for (const viewport of [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'narrow-mobile', width: 320, height: 800 },
]) {
  test(`Wave 5 truth states remain readable at ${viewport.width}×${viewport.height}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/#/intelligence/federal')
    await page.getByRole('button', { name: 'Aerospace precision component sources sought' }).click()
    await expect(page.getByText('Durability not yet established')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
    await screenshot(page, testInfo, `federal-incomplete-${viewport.width}x${viewport.height}.png`)
  })
}
