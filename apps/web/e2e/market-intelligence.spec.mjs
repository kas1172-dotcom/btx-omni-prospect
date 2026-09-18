import { expect, test } from '@playwright/test'

for (const [width, height] of [[320, 800], [390, 844], [768, 1024], [1440, 900]]) {
  test(`market source → trend → unavailable region → canonical account at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height })
    const failures = []
    page.on('pageerror', error => failures.push(error.message))
    await page.goto('/#/intelligence?view=markets&f.market=Semiconductor&f.metric=LEVEL&f.average=0')
    await expect(page.getByRole('heading', { name: 'Market Intelligence', exact: true })).toBeVisible()
    await expect(page.locator('.market-decision > div').first().locator('strong')).toHaveText('191.9')
    await expect(page.locator('.market-decision')).toContainText('2026-07')
    await page.getByLabel('Metric / transformation').selectOption('YOY_PERCENT')
    await expect(page.locator('.market-decision')).toContainText('Year-over-year change')
    await expect(page.getByRole('table')).toContainText('Semiconductor')
    await expect(page.getByText('It does not establish an account order, regional demand', { exact: false })).toBeVisible()
    await page.getByLabel('BTX market').selectOption('Robotics')
    await expect(page.getByText('No verified production series is available', { exact: false })).toBeVisible()
    await page.goBack()
    await expect(page.getByLabel('BTX market')).toHaveValue('Semiconductor')
    await page.reload()
    await expect(page.getByLabel('Metric / transformation')).toHaveValue('YOY_PERCENT')
    await expect(page.locator('.market-decision')).toContainText('2026-07')
    await page.getByText('Source, transformation and vintage evidence', { exact: true }).click()
    await expect(page.locator('.market-intelligence')).toContainText('NAICS2022')
    await expect(page.locator('.market-intelligence')).toContainText('NOT_YET_CONFIGURED')
    await expect(page.locator('.market-intelligence')).toContainText('Publication date unavailable; retrieval date is not substituted')
    const overflow = await page.evaluate(() => ({ amount: document.documentElement.scrollWidth - innerWidth, offenders: [...document.querySelectorAll('*')].filter(element => element.getBoundingClientRect().right > innerWidth + 1).slice(0, 8).map(element => `${element.tagName.toLowerCase()}.${element.className}`) }))
    expect(overflow.amount, `overflowing elements: ${overflow.offenders.join(', ')}`).toBeLessThanOrEqual(1)
    await page.screenshot({ path: testInfo.outputPath(`market-${width}.png`), fullPage: true })
    await page.evaluate(() => scrollTo(0, 0))
    await page.screenshot({ path: testInfo.outputPath(`market-viewport-${width}.png`) })
    await page.getByRole('region', { name: 'Canonical account exposure' }).getByRole('button', { name: 'KLA Corporation', exact: true }).click()
    await expect(page).toHaveURL(/#\/accounts\/kla\?.*return=/)
    expect(failures).toEqual([])
  })
}

test('market errors retain filters and recover through the same API', async ({ page }) => {
  let fail = true
  await page.route('**/api/markets?*', route => fail ? route.fulfill({ status: 503, body: 'Unavailable' }) : route.continue())
  await page.goto('/#/intelligence?view=markets&f.market=Semiconductor&f.metric=LEVEL&f.average=0')
  await expect(page.getByRole('alert')).toContainText('Market observations unavailable')
  await expect(page.getByLabel('Metric / transformation')).toHaveValue('LEVEL')
  fail = false
  await page.getByRole('button', { name: 'Refresh saved observations' }).click()
  await expect(page.locator('.market-decision > div').first()).toContainText('191.9')
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('market comparisons enforce compatibility and retain last-good observations during a failed refresh', async ({ page }) => {
  let fail = false
  await page.route('**/api/markets?*', async route => fail ? route.fulfill({ status: 503, body: 'Unavailable' }) : route.continue())
  await page.goto('/#/intelligence?view=markets&f.market=Semiconductor&f.metric=LEVEL&f.average=0')
  await expect(page.locator('.market-decision')).toContainText('191.9')
  await page.getByLabel('Compare with').selectOption('Medical')
  await expect(page.getByRole('table', { name: /Aligned national series comparison/ })).toContainText('Medical')
  fail = true
  await page.getByRole('button', { name: 'Refresh saved observations' }).click()
  await expect(page.getByRole('alert')).toContainText('Last-good observations remain visible')
  await expect(page.locator('.market-decision')).toContainText('191.9')

  fail = false
  await page.unrouteAll({ behavior: 'wait' })
  await page.route('**/api/markets?*', async route => {
    const response = await route.fetch()
    const data = await response.json()
    const medical = data.series.find(item => item.metadata.markets.includes('Medical'))
    if (medical) medical.metadata.unit = 'PERCENT'
    await route.fulfill({ response, json: data })
  })
  await page.reload()
  await expect(page.getByText('Comparison unavailable', { exact: true })).toBeVisible()
  await expect(page.getByText(/unit do not match/)).toBeVisible()
})
