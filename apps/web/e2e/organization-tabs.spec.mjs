import { test, expect } from '@playwright/test'

for (const width of [1440, 390]) {
  test(`organization tabs retain classification and context at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/accounts')
    const login = page.getByLabel('Access code', { exact: true })
    const heading = page.getByRole('heading', { name: 'Accounts', exact: true, level: 1 })
    await expect(login.or(heading)).toBeVisible()
    if (await login.isVisible()) {
      await login.fill('development-salesperson')
      await page.getByRole('button', { name: /Enter Project Beacon/ }).click()
    }
    await expect(heading).toBeVisible()
    const customers = page.getByRole('button', { name: /^Customers \d/ })
    const prospects = page.getByRole('button', { name: /^Prospects \d/ })
    await customers.click()
    await expect(customers).toHaveAttribute('aria-pressed', 'true')
    await prospects.focus(); await page.keyboard.press('Enter')
    await expect(prospects).toHaveAttribute('aria-pressed', 'true')
    await expect(page.getByRole('heading', { name: 'Accounts', level: 1, exact: true })).toBeVisible()
    await expect(page.locator('.portfolio-data-table tbody')).not.toContainText('Classification unavailable')
    await page.reload()
    await expect(prospects).toHaveAttribute('aria-pressed', 'true')
    await customers.click()
    const search = page.getByRole('searchbox', { name: 'Search Customers and Prospects' })
    await search.fill('HUXWRX')
    await page.getByRole('link', { name: 'HUXWRX', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'HUXWRX', exact: true, level: 1 })).toBeVisible()
    await page.getByRole('button', { name: '← Customers & Prospects', exact: true }).click()
    await expect(customers).toHaveAttribute('aria-pressed', 'true')
    await expect(search).toHaveValue('HUXWRX')
    await search.fill('')
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
  })
}
