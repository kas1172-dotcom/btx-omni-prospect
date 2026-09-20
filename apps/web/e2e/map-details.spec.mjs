import { test, expect } from '@playwright/test'

test('selected site shares canonical briefing and exposes evidence without a second account', async ({ page }) => {
  const response = await page.request.get('/api/map')
  expect(response.ok()).toBeTruthy()
  const data = await response.json()
  const record = data.accounts.find(item => item.account_id === 'kla')
  expect(record.commercial_briefing.summary).toBeTruthy()
  await page.goto('/#/map')
  await page.getByRole('region', { name: 'Map results', exact: true }).getByRole('button').filter({ hasText: /^KLA/ }).first().click()
  const panel = page.getByRole('complementary', { name: 'Selected map location', exact: true })
  await panel.getByRole('tab', { name: 'Commercial', exact: true }).click()
  await expect(panel).toContainText(record.commercial_briefing.summary)
  await panel.getByRole('tab', { name: 'Sources', exact: true }).click()
  await panel.getByText('Location and decision evidence', { exact: true }).click()
  await expect(panel.getByText(record.facility_id, { exact: true })).toBeVisible()
  await expect(panel.getByText(record.commercial_briefing.revision, { exact: true })).toBeVisible()
})

test('itinerary persists ordered canonical sites and retains explicit meeting state', async ({ page }) => {
  let mapReads = 0
  page.on('request', request => { if (new URL(request.url()).pathname === '/api/map') mapReads += 1 })
  await page.goto('/#/map')
  const results = page.getByRole('region', { name: 'Map results', exact: true })
  await expect(results).toBeVisible()
  const initialMapReads = mapReads
  await results.getByRole('button').filter({ hasText: /^KLA/ }).first().click()
  await page.getByRole('complementary', { name: 'Selected map location', exact: true }).getByRole('button', { name: 'Add to itinerary', exact: true }).click()
  const itinerary = page.getByRole('dialog', { name: 'Itinerary', exact: true })
  await expect(itinerary).toContainText('1 selected')
  await itinerary.locator('#itinerary-origin').fill('BTX Minneapolis')
  await itinerary.getByRole('button', { name: 'Route-provider details', exact: true }).click()
  await itinerary.getByRole('textbox', { name: 'Origin latitude', exact: true }).fill('44.9778')
  await itinerary.getByRole('textbox', { name: 'Origin longitude', exact: true }).fill('-93.2650')
  await itinerary.getByRole('textbox', { name: 'Visit purpose', exact: true }).fill('Technical fit review')
  await itinerary.getByRole('combobox', { name: 'Meeting status', exact: true }).selectOption('PROPOSED')
  await itinerary.getByRole('button', { name: 'Save itinerary', exact: true }).click()
  await expect(itinerary).toContainText(/Saved version \d+/)
  await itinerary.getByRole('button', { name: 'Close', exact: true }).click()
  await page.getByRole('button', { name: 'Itinerary', exact: true }).click()
  await expect(itinerary.getByRole('textbox', { name: 'Visit purpose', exact: true })).toHaveValue('Technical fit review')
  await expect(itinerary.getByRole('combobox', { name: 'Meeting status', exact: true })).toHaveValue('PROPOSED')
  await expect(itinerary).toContainText('Route timing unavailable')
  await expect(itinerary).not.toContainText('kla ·')
  expect(mapReads).toBe(initialMapReads)
})

test('multi-stop itinerary supports non-drag reorder, removal and refresh persistence', async ({ page }) => {
  await page.goto('/#/map')
  await page.getByRole('button', { name: 'Itinerary', exact: true }).click()
  let itinerary = page.getByRole('dialog', { name: 'Itinerary', exact: true })
  const removeButtons = itinerary.getByRole('button', { name: /^Remove / })
  while (await removeButtons.count()) await removeButtons.first().click()
  if (await itinerary.getByRole('button', { name: 'Save itinerary', exact: true }).isEnabled()) await itinerary.getByRole('button', { name: 'Save itinerary', exact: true }).click()
  await itinerary.getByRole('button', { name: 'Close', exact: true }).click()

  const results = page.getByRole('region', { name: 'Map results', exact: true })
  for (const organization of ['KLA Corporation', 'Boeing']) {
    await results.getByRole('button').filter({ hasText: new RegExp(`^${organization}`) }).first().click()
    await page.getByRole('complementary', { name: 'Selected map location', exact: true }).getByRole('button', { name: 'Add to itinerary', exact: true }).click()
    itinerary = page.getByRole('dialog', { name: 'Itinerary', exact: true })
    await itinerary.getByRole('button', { name: 'Close', exact: true }).click()
  }
  await page.getByRole('button', { name: 'Itinerary', exact: true }).click()
  itinerary = page.getByRole('dialog', { name: 'Itinerary', exact: true })
  await expect(itinerary).toContainText('2 selected')
  await itinerary.getByRole('button', { name: /Move Boeing headquarters earlier/ }).click()
  await itinerary.getByRole('button', { name: 'Save itinerary', exact: true }).click()
  await expect(itinerary).toContainText(/Saved version \d+/)
  await itinerary.getByRole('button', { name: 'Close', exact: true }).click()

  await page.reload()
  await page.getByRole('button', { name: 'Itinerary', exact: true }).click()
  itinerary = page.getByRole('dialog', { name: 'Itinerary', exact: true })
  await expect(itinerary.locator('.itinerary-stops > li').first()).toContainText('Boeing')
  await itinerary.getByRole('button', { name: /Remove Boeing headquarters/ }).click()
  await itinerary.getByRole('button', { name: 'Save itinerary', exact: true }).click()
  await itinerary.getByRole('button', { name: 'Close', exact: true }).click()
  await page.reload()
  await page.getByRole('button', { name: 'Itinerary', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Itinerary', exact: true })).toContainText('1 selected')
  await expect(page.getByRole('dialog', { name: 'Itinerary', exact: true })).not.toContainText('Boeing')
})

test('mobile list switch keeps the selected site when returning to the map', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/map')
  await page.getByRole('button', { name: 'List', exact: true }).click()
  const results = page.getByRole('region', { name: 'Map results', exact: true })
  await expect(results).toBeVisible()
  await results.getByRole('button').filter({ hasText: /^KLA/ }).first().click()
  await expect(page.getByRole('region', { name: 'Tactical Map V2 workspace', exact: true })).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Selected map location', exact: true })).toContainText('KLA')
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})

test('zero score and zero distance are readable values (projection edge-case fixture)', async ({ page }) => {
  await page.route('**/api/map', async route => {
    const response = await route.fetch()
    const data = await response.json()
    for (const item of data.accounts.filter(item => item.account_id === 'kla')) {
      item.attractiveness_score = '0'
      item.nearest_btx_facility = { id: 'fixture-coincident', name: 'Coincident test facility', distance_miles: '0', distance_method: 'HAVERSINE_STRAIGHT_LINE' }
    }
    await route.fulfill({ response, json: data })
  })
  await page.route('**/api/accounts/kla', async route => {
    const response = await route.fetch()
    const data = await response.json()
    data.customer_health.score = '0'
    await route.fulfill({ response, json: data })
  })
  await page.goto('/#/map')
  await page.getByRole('region', { name: 'Map results', exact: true }).getByRole('button').filter({ hasText: /^KLA/ }).first().click()
  const panel = page.getByRole('complementary', { name: 'Selected map location', exact: true })
  await expect(panel.getByLabel('Customer health score summary')).toContainText('0')
  await expect(panel).toContainText('Coincident test facility · 0 miles straight-line')
})
