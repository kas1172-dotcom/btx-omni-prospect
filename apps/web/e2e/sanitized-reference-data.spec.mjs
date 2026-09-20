import { expect, test } from '@playwright/test'
import { openCustomerSection, openOrganizationEvidence } from './helpers.mjs'

async function navigate(page, name) {
  const navigationName = (await page.viewportSize())?.width <= 768 ? 'Mobile primary navigation' : 'Primary navigation'
  await page.getByRole('navigation', { name: navigationName }).getByRole('button', { name }).click()
}

test('sanitized reference Customers, provenance, and BTX Top 100 flow through canonical surfaces', async ({ page }) => {
  await page.goto('/')
  await navigate(page, 'Profiles')
  await page.getByText('+ Filter', { exact: true }).click()
  await page.getByRole('checkbox', { name: 'Top 100', exact: true }).check()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('Honeywell')
  const honeywell = page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('row').filter({ hasText: 'Honeywell' })
  await expect(page.getByRole('checkbox', { name: 'Top 100', exact: true })).toBeChecked()
  expect((await (await page.request.get('/api/accounts/honeywell')).json()).account.btx_top_100).toBe(true)
  await honeywell.getByRole('link', { name: 'Honeywell', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Honeywell', level: 1 })).toBeVisible()
  await openOrganizationEvidence(page)
  await expect(page.getByText(/sanitized-reference-01:Sheet1:/)).toBeVisible()
  await page.locator('.supporting-evidence-trigger').last().click()
  const detail = await (await page.request.get('/api/accounts/honeywell')).json()
  if (detail.commercial_ledger) {
    expect(detail.customer_360.quotes.records.length).toBeGreaterThan(0)
    await openCustomerSection(page, /Commercial context/)
    await page.getByRole('button', { name: /^Recent quotes \/ RFQs/ }).click()
    await expect(page.getByText(detail.customer_360.quotes.records[0].id, { exact: true }).and(page.locator('strong'))).toBeVisible()
  } else await expect(page.getByText('No Quotes / RFQs record is linked to this canonical Customer.')).toBeVisible()

  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  const filters = page.getByRole('dialog', { name: 'Layers & filters' })
  await expect(filters.locator('fieldset').filter({ hasText: 'Visible map layers' }).getByRole('button', { name: 'Customers', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await filters.getByRole('button', { name: 'Apply to map' }).click()
  await page.getByRole('button', { name: /Cluster of .* Customers and Prospects:.*Honeywell/ }).first().click()
  const honeywellMarker = page.getByRole('button', { name: 'Customer marker: Honeywell', exact: true }).first()
  await expect(honeywellMarker).toBeVisible()
  await honeywellMarker.click({ force: true })
  await expect(page.getByRole('complementary', { name: 'Selected map location' })).toContainText('BTX Top 100')
})

for (const width of [390, 320]) test(`expanded reference filters remain usable at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 })
  await page.goto('/')
  await navigate(page, 'Profiles')
  await page.getByText('+ Filter', { exact: true }).click()
  await page.getByRole('checkbox', { name: 'Top 100', exact: true }).check()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('HUXWRX')
  await expect(page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: 'HUXWRX', exact: true })).toBeVisible()
  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await expect(page.getByRole('dialog', { name: 'Layers & filters' }).getByLabel('Strategic partnerships', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})
