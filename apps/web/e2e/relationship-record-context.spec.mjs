import { expect, test } from '@playwright/test'
import { openRelationshipWorkspace } from './helpers.mjs'

for (const width of [390, 1440]) {
  test(`commercial record context preserves ranked authority and opens actual evidence at ${width}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/#/accounts/kla')
    const section = await openRelationshipWorkspace(page)
    const heading = await section.getByRole('heading', { name: /^Selected route/ }).textContent()
    const response = page.waitForResponse(r => r.url().endsWith('/api/relationships/query') && r.request().postDataJSON()?.include_record_context === true)
    await section.getByRole('checkbox', { name: 'Show linked commercial records as context' }).check()
    const result = await (await response).json()
    await expect(section).toHaveAttribute('aria-busy', 'false')
    await expect(section.getByRole('heading', { name: /^Selected route/ })).toHaveText(heading)
    const record = result.graph.edges.find(edge => edge.predicate.startsWith('RECORD_'))
    expect(record).toBeTruthy()
    expect(record.path_ids).toEqual([])
    expect(result.search_complete).toBe(true)
    if (width < 760) await section.getByRole('button', { name: 'Explore network', exact: true }).click()
    const table = section.locator('details').filter({ hasText: 'Visible relationships · keyboard and text equivalent' })
    await table.locator('summary').click()
    await table.getByRole('button').nth(result.graph.edges.findIndex(edge => edge.id === record.id)).click()
    const selected = section.getByRole('combobox', { name: /^Supporting record/ })
    const evidenceResponse = page.waitForResponse(r => r.url().includes('/commercial/evidence?') && r.url().includes(encodeURIComponent(record.evidence_ids[0])))
    await selected.selectOption(record.evidence_ids[0])
    const evidence = await evidenceResponse
    expect(evidence.ok()).toBe(true)
    expect((await evidence.json()).account_id).toBe(record.account_id)
    await expect(section).toContainText(record.evidence_ids[0])
    await expect(section).toContainText('They do not strengthen a route')
    await testInfo.attach('canonical-record-context', { body: JSON.stringify(result.graph, null, 2), contentType: 'application/json' })
    await section.screenshot({ path: testInfo.outputPath(`record-context-${width}.png`) })
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
  })
}
