import { expect, test } from '@playwright/test'

async function navigate(page, name) {
  const navigationName = (await page.viewportSize())?.width <= 768 ? 'Mobile primary navigation' : 'Primary navigation'
  await page.getByRole('navigation', { name: navigationName }).getByRole('button', { name }).click()
}

test('sanitized reference Customers, provenance, and BTX Top 100 flow through canonical surfaces', async ({ page }) => {
  await page.goto('/')
  await navigate(page, 'Customers & Prospects')
  await page.getByRole('button', { name: /Filters/ }).click()
  await page.getByLabel('Customer scope').selectOption('ALL')
  await page.getByRole('button', { name: 'BTX Top 100', exact: true }).click()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('Honeywell')
  const honeywell = page.locator('.portfolio-table-row').filter({ hasText: 'Honeywell' })
  await expect(honeywell).toContainText('BTX Top 100')
  await honeywell.click()
  await expect(page.getByRole('heading', { name: 'Honeywell', level: 1 })).toBeVisible()
  await expect(page.getByText('SANITIZED REFERENCE SOURCE', { exact: true })).toBeVisible()
  await expect(page.getByText('No Paperless record is linked to this canonical Customer.')).toBeVisible()

  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  const filters = page.getByRole('dialog', { name: 'Layers & filters' })
  await filters.getByRole('button', { name: 'BTX Top 100', exact: true }).click()
  await filters.getByRole('button', { name: 'Apply to map' }).click()
  await page.getByRole('button', { name: /Cluster of .* Customers and Prospects:.*Honeywell/ }).first().click()
  await expect(page.getByRole('button', { name: 'Customer marker: Honeywell' })).toBeVisible()
  await page.getByRole('button', { name: 'Customer marker: Honeywell' }).click({ force: true })
  await expect(page.getByRole('complementary', { name: 'Selected map location' })).toContainText('BTX Top 100')
})

for (const width of [390, 320]) test(`expanded reference filters remain usable at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 })
  await page.goto('/')
  await navigate(page, 'Customers & Prospects')
  await page.getByRole('button', { name: /Filters/ }).click()
  await page.getByRole('button', { name: 'BTX Top 100', exact: true }).click()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('HUXWRX')
  await expect(page.locator('.portfolio-mobile-list .ui-mobile-row').filter({ hasText: 'HUXWRX' })).toBeVisible()
  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await expect(page.getByRole('dialog', { name: 'Layers & filters' }).getByRole('button', { name: 'BTX Top 100', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})
