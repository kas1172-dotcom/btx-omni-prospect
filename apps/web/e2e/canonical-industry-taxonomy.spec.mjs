import { expect, test } from '@playwright/test'

async function navigate(page, name) {
  const navigationName = (await page.viewportSize())?.width <= 768 ? 'Mobile primary navigation' : 'Primary navigation'
  await page.getByRole('navigation', { name: navigationName }).getByRole('button', { name }).click()
}

test('canonical industries compose across Portfolio, Intelligence, and Map', async ({ page }) => {
  await page.goto('/')
  await navigate(page, 'Customers & Prospects')
  await page.getByRole('button', { name: /Filters/ }).click()
  await page.getByLabel('Customer scope').selectOption('ALL')
  for (const industry of ['Defense', 'Commercial Aerospace', 'Space', 'Robotics', 'Semiconductor', 'Medical', 'Energy']) {
    await expect(page.getByRole('button', { name: industry, exact: true })).toBeVisible()
  }
  await expect(page.getByRole('button', { name: 'Aerospace', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Space Exploration', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Robotics', exact: true }).click()
  await expect(page.locator('.account-row').filter({ hasText: 'Symbotic' })).toBeVisible()

  await navigate(page, 'Intelligence')
  await page.getByLabel('Filter Intelligence by market').selectOption({ label: 'Robotics' })
  await expect(page.locator('.intelligence-card').filter({ hasText: 'Symbotic' })).toBeVisible()

  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  const sheet = page.getByRole('dialog', { name: 'Layers & filters' })
  await sheet.getByRole('button', { name: 'All researched' }).click()
  await sheet.getByRole('button', { name: 'Defense', exact: true }).click()
  await sheet.getByRole('button', { name: 'Commercial Aerospace', exact: true }).click()
  await sheet.getByRole('button', { name: 'Apply to map' }).click()
  await page.getByRole('button', { name: /Cluster of .* Customers and Prospects:.*Lockheed Martin/ }).first().click()
  await expect(page.getByRole('button', { name: 'Customer marker: Lockheed Martin', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Customer marker: Boeing', exact: true }).first()).toBeVisible()
})

for (const width of [390, 320]) test(`canonical industry controls remain usable at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 })
  await page.goto('/')
  await navigate(page, 'Customers & Prospects')
  await page.getByRole('button', { name: /Filters/ }).click()
  await expect(page.getByRole('button', { name: 'Commercial Aerospace', exact: true })).toBeVisible()
  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await expect(page.getByRole('dialog', { name: 'Layers & filters' }).getByRole('button', { name: 'Commercial Aerospace', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})
