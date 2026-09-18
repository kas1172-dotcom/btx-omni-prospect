import { expect, test } from '@playwright/test'

test('private usage loads independently and a failed refresh preserves prior values', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
  let calls = 0
  let fail = false
  await page.route('**/api/settings/ai-usage', async route => {
    calls += 1
    if (fail) await route.fulfill({ status: 503, body: 'Temporarily unavailable' })
    else await route.continue()
  })
  await page.goto('/#/settings')
  const summary = page.getByText('AI call budget and usage', { exact: true })
  await expect(summary).toBeVisible()
  expect(calls).toBe(0)
  await summary.click()
  const panel = page.locator('.ui-disclosure').filter({ has: summary })
  await expect(panel).toContainText('BTX_AI_CALL_BUDGET_1')
  await expect(panel).toContainText('Not measured; consult provider billing')
  fail = true
  await panel.getByRole('button', { name: 'Refresh AI usage' }).click()
  await expect(panel.getByRole('alert')).toContainText('prior values, if shown, are not current')
  await expect(panel).toContainText('BTX_AI_CALL_BUDGET_1')
  fail = false
  await panel.getByRole('button', { name: 'Refresh AI usage' }).click()
  await expect(panel.getByRole('alert')).toHaveCount(0)
  await expect(panel.getByRole('button', { name: 'Refresh AI usage' })).toBeEnabled()
  await panel.evaluate(element => element.scrollIntoView({ block: 'start' }))
  await page.screenshot({ path: testInfo.outputPath('ai-usage-mobile.png') })
  await expect(page.locator('html')).toHaveJSProperty('scrollWidth', 390)
})
