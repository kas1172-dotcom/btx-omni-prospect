import { expect, test } from '@playwright/test'

const sorted = values => [...values].sort((left, right) => left.localeCompare(right))

async function desktopDestinations(page) {
  const primary = await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button').allTextContents()
  const secondary = await page.locator('.sidebar-footer > button').allTextContents()
  return sorted([...primary, ...secondary].map(value => value.trim()).filter(Boolean))
}

async function mobileDestinations(page) {
  const mobileNavigation = page.getByRole('navigation', { name: 'Mobile primary navigation' })
  const primary = await mobileNavigation.getByRole('button').filter({ hasNotText: /^More$/ }).allTextContents()
  const menu = mobileNavigation.getByRole('button', { name: 'More', exact: true })
  if (await menu.getAttribute('aria-expanded') !== 'true') await menu.click()
  const secondary = await page.locator('.mobile-secondary-links > button').evaluateAll(buttons => buttons.map(button => button.getAttribute('aria-label') ?? button.textContent ?? ''))
  return sorted([...primary, ...secondary].map(value => value.trim()).filter(Boolean))
}

test('seller navigation is consistent and permission-safe on direct Source Health access', async ({ page }) => {
  let sourceHealthRequests = 0
  await page.route('**/api/monitor/health', async route => { sourceHealthRequests += 1; await route.continue() })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await expect(page.getByLabel('Signed-in user')).toContainText('Development Salesperson')
  const desktop = await desktopDestinations(page)
  expect(desktop).toEqual(sorted(['Today', 'Opportunities', 'Profiles', 'Intelligence', 'Map', 'Actions', 'Communications', 'Settings']))
  await expect(page.getByRole('button', { name: 'Source Health', exact: true })).toHaveCount(0)

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await mobileDestinations(page)).toEqual(desktop)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)

  await page.goto('/#/monitor')
  await expect(page.getByRole('heading', { name: 'Today', exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('unavailable for your current access')
  await expect(page.getByRole('heading', { name: 'Source Health', exact: true })).toHaveCount(0)
  expect(sourceHealthRequests).toBe(0)
  const denied = await page.request.get('/api/monitor/health', { headers: { 'X-BTX-Principal-Token': 'development-salesperson' } })
  expect(denied.status()).toBe(403)
  expect(await denied.text()).not.toMatch(/sam\.gov|scheduler_state|source_id|records_seen/i)

  const menu = page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button', { name: 'More', exact: true })
  if (await menu.getAttribute('aria-expanded') !== 'true') await menu.click()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Settings sections' }).getByRole('link', { name: 'Integrations' })).toHaveCount(0)
  await expect(page.getByText('Google Maps', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Safe release diagnostics', { exact: true })).toHaveCount(0)

  await page.goto('/#/settings/integrations')
  await expect(page).toHaveURL(/#\/settings\?view=access$/)
  await expect(page.getByRole('alert')).toContainText('unavailable for your current access')
  await expect(page.getByText('Google Maps', { exact: true })).toHaveCount(0)
})

test('administrator has desktop/mobile Source Health parity, durable navigation, and disclosed diagnostics', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await context.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.getByLabel('Signed-in user')).toContainText('Development Manager')
  const desktop = await desktopDestinations(page)
  expect(desktop).toContain('Source Health')

  const sourceHealth = page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Source Health', exact: true })
  await sourceHealth.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: 'Source Health', exact: true })).toBeVisible()
  await expect(page.getByLabel('Source Health summary')).toBeVisible()
  await expect(page.getByText('Operator decision', { exact: true })).toBeVisible()
  const runHistory = page.getByRole('button', { name: /Run history and exact diagnostics/ })
  await runHistory.focus()
  await page.keyboard.press('Enter')
  await expect(runHistory).toHaveAttribute('aria-expanded', 'true')
  await expect(page).toHaveURL(/#\/monitor$/)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Source Health', exact: true })).toBeVisible()

  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Today', exact: true }).click()
  await page.goBack()
  await expect(page.getByRole('heading', { name: 'Source Health', exact: true })).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await mobileDestinations(page)).toEqual(desktop)
  await expect(page.getByRole('dialog', { name: 'More' })).toBeVisible()
  await expect(page.locator('.mobile-secondary-links').getByRole('button', { name: 'Source Health', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)

  await page.locator('.mobile-secondary-links').getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('navigation', { name: 'Settings sections' }).getByRole('link', { name: 'Integrations' })).toBeVisible()
  await context.close()
})
