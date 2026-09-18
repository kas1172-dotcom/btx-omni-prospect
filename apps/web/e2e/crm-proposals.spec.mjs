import { test, expect } from '@playwright/test'

for (const width of [390, 1440]) {
  test(`exact CRM proposal approval and uncertain sample retry persist at ${width}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await page.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
    const title = `CRM recovery review ${crypto.randomUUID()}`
    const created = await page.request.post('/api/actions', { data: { account_id: 'boeing', title,
      description: 'Review remaining deliveries; do not promise capacity or a substitute.', idempotency_key: crypto.randomUUID() } })
    expect(created.ok()).toBeTruthy()
    const action = await created.json()
    await page.goto('/#/actions')
    await page.getByLabel('Search actions').fill(title)
    await expect(page.getByText('1 filtered · 1 displayed')).toBeVisible()
    await page.locator('.action-row').first().click()
    await expect(page).toHaveURL(new RegExp(`action=${action.id}`))
    const panel = page.locator('.crm-proposal-panel')
    await panel.locator(':scope > summary').click()
    await panel.getByRole('button', { name: 'Prepare exact CRM proposal', exact: true }).click()
    await expect(panel.getByRole('status').filter({ hasText: 'Exact proposal saved' })).toBeVisible()
    await expect(panel).toContainText(title)
    await expect(panel).toContainText('Local HubSpot workflow demonstration — no HubSpot account will be changed')
    await panel.getByRole('button', { name: 'Approve exact proposal', exact: true }).click()
    await expect(panel.getByText('Proposal approval: Approved by reviewer', { exact: true })).toBeVisible()
    let lost = false
    await page.route('**/crm-execute?confirmed=true', async route => {
      const response = await route.fetch()
      if (!lost) { lost = true; expect(response.ok()).toBeTruthy(); await route.abort('failed') }
      else await route.fulfill({ response })
    })
    await panel.getByRole('button', { name: 'Run approved controlled attempt', exact: true }).click()
    await expect(panel.getByRole('alert')).toContainText('Refresh to inspect saved receipts')
    await panel.getByRole('button', { name: 'Run approved controlled attempt', exact: true }).click()
    await expect(panel.getByRole('status').filter({ hasText: 'Saved receipt recovered' })).toBeVisible()
    await expect(panel.getByRole('button', { name: 'Run approved controlled attempt', exact: true })).toBeDisabled()
    const receipt = await page.request.get(`/api/actions/${action.id}/crm-proposals`)
    expect(receipt.ok()).toBeTruthy()
    const history = await receipt.json()
    expect(history.events.filter(item => item.kind === 'CRM_SAMPLE_ATTEMPT')).toHaveLength(1)
    expect(history.events.find(item => item.kind === 'CRM_SAMPLE_ATTEMPT').data.external_write).toBe(false)
    await page.reload()
    await page.getByLabel('Search actions').fill(title)
    await expect(page.getByText('1 filtered · 1 displayed')).toBeVisible()
    await page.locator('.action-row').first().click()
    await panel.locator(':scope > summary').click()
    await expect(panel).toContainText('Controlled attempt completed — no external CRM write')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await panel.evaluate(element => element.scrollIntoView({ block: 'start' }))
    await page.screenshot({ path: testInfo.outputPath('crm-sample-workflow.png') })
  })
}
