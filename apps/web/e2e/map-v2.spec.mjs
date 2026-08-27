import { expect, test } from '@playwright/test'

async function openMap(page) {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Map' }).click()
  await expect(page.getByRole('heading', { name: 'Tactical Map' })).toBeVisible()
}

test('Map V2 is marker-first and opens canonical Customer context', async ({ page }) => {
  await openMap(page)
  await expect(page.getByRole('region', { name: 'Tactical Map V2 workspace' })).toBeVisible()
  await expect(page.locator('.map-layout')).toHaveCount(0)
  const customer = page.getByRole('button', { name: 'Customer marker: Lockheed Martin' })
  await customer.click()
  await expect(customer).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('complementary', { name: 'Selected map location' })).toContainText('Lockheed Martin')
  await page.getByRole('button', { name: 'View Customer' }).click()
  await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
})

test('Map V2 reports missing Google browser configuration truthfully', async ({ page }) => {
  await page.goto('/?map-test-unconfigured=1')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Map' }).click()
  await expect(page.getByRole('heading', { name: 'Map not configured' })).toBeVisible()
  await expect(page.getByText('Google Maps browser configuration is required')).toBeVisible()
})

for (const width of [390, 320]) test(`Map V2 mobile sheets remain reachable at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 })
  await openMap(page)
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  const sheet = page.getByRole('dialog', { name: 'Layers & filters' })
  await expect(sheet).toBeVisible()
  await sheet.getByRole('button', { name: 'Intelligence' }).click()
  await sheet.getByRole('button', { name: 'Apply to map' }).click()
  const marker = page.getByRole('button', { name: /Customer marker:/ }).first()
  await marker.click()
  await expect(page.getByRole('complementary', { name: 'Selected map location' })).toBeVisible()
  await expect(page.getByLabel('Open Omni assistant')).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})
