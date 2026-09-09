import { expect, test } from '@playwright/test'

for (const [width, height] of [[360, 800], [390, 844], [768, 1024], [1440, 900], [1920, 1080]]) {
  test(`market source → trend → unavailable region → canonical account at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height })
    const failures = []
    page.on('pageerror', error => failures.push(error.message))
    await page.goto('/#/intelligence/markets?market=Semiconductor&metric=LEVEL&average=0')
    await expect(page.getByRole('heading', { name: 'Market Intelligence', exact: true })).toBeVisible()
    await expect(page.locator('.market-scorecard strong')).toHaveText('191.9')
    await expect(page.locator('.market-scorecard')).toContainText('2026-07')
    await page.getByLabel('Metric / transformation').selectOption('YOY_PERCENT')
    await expect(page.locator('.market-scorecard')).toContainText('Year-over-year change')
    await expect(page.getByRole('table')).toContainText('Semiconductor')
    await page.getByText('Regional availability', { exact: true }).click()
    await expect(page.getByText('Regional industrial production for these industry series is unavailable.', { exact: false })).toBeVisible()
    await page.getByLabel('BTX market').selectOption('Robotics')
    await expect(page.getByText('No verified production series is available', { exact: false })).toBeVisible()
    await page.goBack()
    await expect(page.getByLabel('BTX market')).toHaveValue('Semiconductor')
    await page.reload()
    await expect(page.getByLabel('Metric / transformation')).toHaveValue('YOY_PERCENT')
    await expect(page.locator('.market-scorecard')).toContainText('2026-07')
    await page.getByText('Source, vintage and coverage audit', { exact: true }).click()
    await expect(page.locator('.market-intelligence')).toContainText('NAICS2022')
    await expect(page.locator('.market-intelligence')).toContainText('NOT_YET_CONFIGURED')
    await expect(page.locator('.market-intelligence')).toContainText('Not extracted; retrieval date is not publication date')
    await page.getByText('Source, vintage and coverage audit', { exact: true }).click()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)
    expect(overflow).toBe(false)
    await page.screenshot({ path: testInfo.outputPath(`market-${width}.png`), fullPage: true })
    await page.evaluate(() => scrollTo(0, 0))
    await page.screenshot({ path: testInfo.outputPath(`market-viewport-${width}.png`) })
    await page.getByRole('region', { name: 'Canonical account exposure' }).getByRole('button', { name: 'KLA Corporation', exact: true }).click()
    await expect(page).toHaveURL(/#\/accounts\/kla$/)
    expect(failures).toEqual([])
  })
}

test('market errors retain filters and recover through the same API', async ({ page }) => {
  let fail = true
  await page.route('**/api/markets?*', route => fail ? route.fulfill({ status: 503, body: 'Unavailable' }) : route.continue())
  await page.goto('/#/intelligence/markets?market=Semiconductor&metric=LEVEL&average=0')
  await expect(page.getByRole('alert')).toContainText('Market data could not be loaded')
  await expect(page.getByLabel('Metric / transformation')).toHaveValue('LEVEL')
  fail = false
  await page.getByRole('button', { name: 'Refresh saved observations' }).click()
  await expect(page.locator('.market-scorecard strong')).toHaveText('191.9')
  await expect(page.getByRole('alert')).toHaveCount(0)
})
