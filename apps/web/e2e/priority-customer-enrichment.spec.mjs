import { expect, test } from '@playwright/test'

const priorityCustomers = [
  'Honeywell', 'Boeing', 'KLA Corporation', 'SpaceX', 'Intuitive Surgical',
  'Lockheed Martin', 'Woodward', 'Northrop Grumman', 'HUXWRX', 'Eaton', 'Emerson',
]

async function openPortfolio(page) {
  const navigationName = (await page.viewportSize())?.width <= 768 ? 'Mobile primary navigation' : 'Primary navigation'
  await page.goto('/')
  await page.getByRole('navigation', { name: navigationName }).getByRole('button', { name: 'Customers & Prospects' }).click()
}

test('all priority Customers are discoverable and rich/reference scenarios remain truthful', async ({ page }) => {
  await openPortfolio(page)
  const search = page.getByRole('searchbox', { name: 'Search Customers and Prospects' })
  for (const name of priorityCustomers) {
    await search.fill(name)
    await expect(page.locator('.portfolio-table-row').filter({ hasText: name })).toHaveCount(1)
  }

  await search.fill('Honeywell')
  await page.locator('.portfolio-table-row').filter({ hasText: 'Honeywell' }).click()
  await expect(page.getByRole('heading', { name: 'Honeywell', level: 1 })).toBeVisible()
  await expect(page.getByText('SANITIZED REFERENCE SOURCE', { exact: true })).toBeVisible()
  await expect(page.getByText('SIMULATED BTX CONTEXT', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Commercial context available')).toBeVisible()
  await expect(page.getByText('Cross Bu Coordination')).toBeVisible()
  await expect(page.getByText('No verified public contact is available.', { exact: false })).toBeVisible()

  await page.getByRole('searchbox', { name: 'Switch Customer' }).fill('HUXWRX')
  await page.getByRole('option', { name: /HUXWRX/ }).click()
  await expect(page.getByRole('heading', { name: 'HUXWRX', level: 1 })).toBeVisible()
  await expect(page.getByText('No Commercial record is linked to this canonical Customer.')).toBeVisible()
  await expect(page.getByText('No governed alert is currently open')).toBeVisible()
  await expect(page.getByText('No eligible validated connection is currently available for this Customer.')).toBeVisible()
})

for (const width of [390, 320]) test(`priority Customer disclosures remain usable at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 })
  await openPortfolio(page)
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('Eaton')
  await page.locator('.portfolio-mobile-list .ui-mobile-row').filter({ hasText: 'Eaton' }).click()
  await expect(page.getByRole('heading', { name: 'Eaton', level: 1 })).toBeVisible()
  const attention = page.getByRole('button', { name: /What needs attention/ })
  await expect(attention).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByText('BOOKINGS DECLINE', { exact: true })).toBeVisible()
  const commercial = page.getByRole('button', { name: /Commercial context/ })
  await commercial.click()
  await expect(commercial).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByText('Simulated BTX commercial context')).toBeVisible()
  await expect(page.getByLabel('Open Omni assistant')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})
