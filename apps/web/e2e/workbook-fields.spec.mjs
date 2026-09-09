import { test, expect } from '@playwright/test'

for (const width of [390, 1440]) {
  test(`original workbook cells load privately and retain disclosure state at ${width}`, async ({ page }, testInfo) => {
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await page.goto('/#/accounts/kla')
    const disclosure = page.locator('.workbook-fields')
    await disclosure.locator(':scope > summary').click()
    const response = await page.request.get('/api/accounts/kla/workbook-fields')
    expect(response.ok()).toBeTruthy()
    expect(response.headers()['cache-control']).toContain('no-store')
    const result = await response.json()
    expect(result.total).toBeGreaterThan(0)
    const row = result.items[0]
    const source = disclosure.locator('summary').filter({ hasText: `${row.workbook} · ${row.sheet} · row ${row.row_number}` })
    await source.click()
    for (const field of row.fields) {
      await expect(disclosure.getByText(`${field.label}`, { exact: false }).first()).toBeVisible()
    }
    expect(typeof row.source_organization).toBe('string')
    await expect(disclosure).toContainText(row.source_organization)
    await disclosure.locator(':scope > summary').click()
    await disclosure.locator(':scope > summary').click()
    await expect(disclosure.getByText(`Original organization: ${row.source_organization}`, { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    const historic = await page.request.get(`/api/accounts/kla/workbook-fields/${row.version_id}`)
    expect((await historic.json()).fields).toEqual(row.fields)
    expect((await page.request.get(`/api/accounts/boeing/workbook-fields/${row.version_id}`)).status()).toBe(404)
    await disclosure.scrollIntoViewIfNeeded()
    await page.screenshot({ path: testInfo.outputPath('original-workbook-fields.png') })
    expect(errors).toEqual([])
  })
}
