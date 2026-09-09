import { expect, test } from '@playwright/test'

test('lost memory-save response retries once without duplication; deletion blocks resurrection', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/settings')
  const panel = page.getByRole('region', { name: 'Private Omni preferences' })
  const content = `Retry preference ${testInfo.testId}: show evidence dates`
  await panel.getByLabel('Preference', { exact: true }).fill(content)
  let requestBody
  let loseFirst = true
  await page.route('**/api/omni/memories', async route => {
    if (route.request().method() === 'POST' && loseFirst) {
      requestBody = route.request().postDataJSON()
      const response = await route.fetch()
      expect(response.ok()).toBe(true)
      loseFirst = false
      await route.abort('failed')
    } else await route.continue()
  })
  await panel.getByRole('button', { name: 'Save private preference', exact: true }).click()
  await expect(panel).toContainText('Refresh and inspect your saved preferences')
  await panel.getByRole('button', { name: 'Save private preference', exact: true }).click()
  await expect(panel).toContainText('The original save was already recorded.')
  let data = await (await page.request.get('/api/omni/memories')).json()
  expect(data.items.filter(item => item.content === content)).toHaveLength(1)
  const record = panel.locator('.omni-memory-record').filter({ hasText: content })
  await record.getByRole('button', { name: 'Delete preference', exact: true }).click()
  await record.getByRole('button', { name: 'Confirm delete', exact: true }).click()
  await expect(record).toHaveCount(0)
  const replay = await page.request.post('/api/omni/memories', { data: requestBody })
  expect(replay.status()).toBe(409)
  data = await (await page.request.get('/api/omni/memories')).json()
  expect(data.items.filter(item => item.content === content)).toHaveLength(0)
  await expect(page.locator('html')).toHaveJSProperty('scrollWidth', 390)
})

test('an unsaved private memory draft survives navigation for the same principal', async ({ page }, testInfo) => {
  await page.goto('/#/settings')
  const content = `Unsaved navigation draft ${testInfo.testId}`
  await page.getByRole('region', { name: 'Private Omni preferences' }).getByLabel('Preference', { exact: true }).fill(content)
  await page.getByRole('button', { name: 'Today', exact: true }).click()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Private Omni preferences' }).getByLabel('Preference', { exact: true })).toHaveValue(content)
})
