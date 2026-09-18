import { test, expect } from '@playwright/test'

test('durable real collection diagnostics and rejected public passages are inspectable without seller promotion', async ({ page }, testInfo) => {
  await page.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
  const healthResponse = await page.request.get('/api/monitor/health', { headers: { 'X-BTX-Principal-Token': 'development-manager' } })
  expect(healthResponse.ok()).toBeTruthy()
  const health = await healthResponse.json()
  expect(health.durable_run_state).toBe(true)
  const run = health.last_runs.find(item => item.funnel?.version === 'BTX_COLLECTION_FUNNEL_1')
  expect(run).toBeTruthy()
  expect(Array.isArray(run.failures)).toBe(true)
  let selected
  for (const event of health.events.filter(item => item.seller_relevance_state === 'REJECTED' && item.is_current_source_version !== false)) {
    const response = await page.request.get(`/api/intelligence/${event.id}/evidence`)
    const evidence = await response.json()
    if (evidence.document?.passages.length) { selected = { event, evidence }; break }
  }
  expect(selected).toBeTruthy()
  await page.goto('/#/monitor')
  const diagnostics = page.locator('.monitor-run-funnel').filter({ hasText: run.id })
  await diagnostics.locator('summary').click()
  await expect(diagnostics).toContainText('BTX_COLLECTION_FUNNEL_1')
  const source = page.locator('.monitor-collected-record').filter({ hasText: selected.event.id })
  await source.locator(':scope > summary').click()
  await source.getByText('Inspect retained public passages', { exact: true }).click()
  await expect(source.getByText(selected.evidence.title, { exact: true })).toBeVisible()
  await source.locator('summary').filter({ hasText: /^Passage · characters/ }).first().click()
  await expect(source.locator('blockquote').first()).toHaveText(selected.evidence.document.passages[0].text)
  await expect(source).toContainText(selected.evidence.document.checksum_sha256)
  await expect(page.locator('.monitor-live-list').getByText(selected.evidence.title, { exact: true })).toHaveCount(0)
  await testInfo.attach('public-evidence-lineage', { body: JSON.stringify({ run_id: run.id, event_id: selected.event.id, observation_id: selected.evidence.observation_id, checksum: selected.evidence.document.checksum_sha256, source_url: selected.evidence.source_url }, null, 2), contentType: 'application/json' })
  await source.screenshot({ path: testInfo.outputPath('retained-public-passages.png') })
})
