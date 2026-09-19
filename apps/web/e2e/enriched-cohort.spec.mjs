import { test, expect } from '@playwright/test'

const accounts = ['honeywell', 'boeing', 'kla', 'spacex', 'intuitive-surgical', 'lockheed-martin', 'woodward', 'northrop-grumman', 'huxwrx', 'eaton', 'emerson']

test('all eleven persisted enriched accounts have distinct briefings and twelve-month records in the seller UI', async ({ page }, testInfo) => {
  const evidence = []
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  for (const id of accounts) {
    const accountResponse = await page.request.get(`/api/accounts/${id}`)
    expect(accountResponse.ok()).toBeTruthy()
    const account = await accountResponse.json()
    // This is the enriched-release gate, not the legacy thin-reference fixture gate.
    expect(account.commercial_briefing?.account_id).toBe(id)
    expect(account.commercial_briefing.evidence_ids.length).toBeGreaterThan(0)
    const historyResponse = await page.request.get(`/api/accounts/${id}/commercial/monthly_commercial_history`)
    expect(historyResponse.ok()).toBeTruthy()
    const history = await historyResponse.json()
    expect(history.total).toBe(12)
    expect(new Set(history.records.map(row => row.period)).size).toBe(12)
    expect(history.revision).toBe(account.commercial_briefing.revision)
    await page.goto(`/#/accounts/${id}`)
    await expect(page.getByRole('heading', { name: account.account.name ?? account.account.legal_name, exact: true, level: 1 })).toBeVisible()
    const decision = page.getByRole('region', { name: 'Organization decision summary' })
    const briefings = account.customer_360.intelligence.map(item => item.business_briefing).filter(Boolean)
    const expansion = account.organization_360.expansion_pursuit
    const currentAssessment = expansion ? briefings.find(item => item.assessment_id === expansion.assessment_id) ?? briefings[0] : briefings[0]
    await expect(decision).toContainText(currentAssessment?.headline ?? account.intelligence[0]?.title ?? account.commercial_briefing.summary)
    await expect(decision).toContainText(expansion?.governed_action ?? currentAssessment?.recommended_action ?? account.recommended_next_step ?? account.commercial_briefing.next_action)
    evidence.push({ id, revision: history.revision, periods: history.records.map(row => row.period), briefing: account.commercial_briefing })
  }
  expect(new Set(evidence.map(item => item.briefing.summary)).size).toBe(accounts.length)
  expect(errors).toEqual([])
  await testInfo.attach('canonical-cohort-evidence', { body: JSON.stringify(evidence, null, 2), contentType: 'application/json' })
})

for (const [width, height] of [[360, 800], [390, 844], [768, 1024], [1440, 900], [1920, 1080]]) {
  test(`enriched account reading is contained at ${width}x${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('/#/accounts/kla')
    await expect(page.getByRole('heading', { name: 'KLA Corporation', exact: true, level: 1 })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Organization decision summary' })).toContainText('New cleaning and inspection scope changed the current quote')
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
    await expect(page.getByLabel('Open Omni assistant')).toBeVisible()
    await expect(page.getByRole('complementary', { name: 'Demonstration environment', exact: true })).toHaveCount(1)
    if (width <= 760) {
      const more = await page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button', { name: 'More', exact: true }).boundingBox()
      const omni = await page.getByLabel('Open Omni assistant').boundingBox()
      expect(more).not.toBeNull()
      expect(omni).not.toBeNull()
      expect((more?.y ?? 0)).toBeGreaterThan((omni?.y ?? 0) + (omni?.height ?? 0))
    }
    expect(errors).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`kla-${width}x${height}.png`) })
  })
}
