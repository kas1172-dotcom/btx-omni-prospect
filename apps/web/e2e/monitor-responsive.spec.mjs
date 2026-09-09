import { expect, test } from '@playwright/test'

// Deterministic layout stress only. Actual public collection and research
// evidence are qualified separately by monitor-public-evidence.spec.mjs.
for (const width of [320, 390, 1440]) {
  test(`Monitor keeps long source diagnostics readable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.route('**/api/monitor/health', async route => {
      const response = await route.fetch()
      const health = await response.json()
      await route.fulfill({ response, json: { ...health, sources: [{ ...health.sources[0],
        source_id: 'source-layout-regression',
        source_name: 'US Department of Defense Contract Announcements',
        state: 'NOT_CONFIGURED', last_success_at: null,
        failure_summary: 'BTX_MONITOR_STATE_SOURCE_REGISTRY has no configured sources.',
      }] } })
    })
    await page.goto('/#/monitor')
    const source = page.locator('.monitor-source-list .line').first()
    await expect(source).toContainText('BTX_MONITOR_STATE_SOURCE_REGISTRY')
    await expect(source).toContainText('NOT CONFIGURED')
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
    const panel = await source.locator('xpath=ancestor::*[contains(@class,"panel")][1]').boundingBox()
    const row = await source.boundingBox()
    expect(row.x + row.width).toBeLessThanOrEqual(panel.x + panel.width)
  })
}
