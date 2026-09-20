import { expect, test } from '@playwright/test'

for (const [screen, search, label] of [
  ['actions', 'Search actions', 'Actions'],
  ['communications', 'Search communications', 'Communications'],
  ['intelligence', 'Search Intelligence', 'Intelligence'],
  ['accounts', 'Search Customers and Prospects', 'Customers & Prospects'],
]) test(`${label} chips, clear-all, URL reload and navigation preserve filters`, async ({ page }) => {
  await page.goto(`/#/${screen}`)
  const input = page.getByLabel(search, { exact: true })
  await input.fill('no-match-xyz-unique')
  await expect(page).toHaveURL(/f.query=no-match-xyz-unique/)
  const chips = page.locator('.applied-filter-chips').first()
  await expect(chips.getByRole('button', { name: /Remove (Search|search): no-match-xyz-unique filter/i })).toBeVisible()
  await expect(chips).toContainText('0 results')
  await page.reload()
  await expect(input).toHaveValue('no-match-xyz-unique')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Today', exact: true }).click()
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: label, exact: true }).click()
  await expect(input).toHaveValue('no-match-xyz-unique')
  await chips.getByRole('button', { name: /^Remove .*no-match-xyz-unique/ }).click()
  await expect(input).toHaveValue('')
  await input.fill('another-no-match-xyz')
  await chips.getByRole('button', { name: 'Clear all', exact: true }).click()
  await expect(input).toHaveValue('')
  await expect(page).not.toHaveURL(/f.query=/)
})

test('narrow filters expose active count and keep desktop facets visible without a menu', async ({ page }) => {
  await page.goto('/#/actions?f.priority=HIGH')
  await expect(page.getByLabel('Filter by priority')).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByLabel('Filter by priority')).toBeHidden()
  const trigger = page.locator('.filter-mobile-trigger')
  await expect(trigger).toContainText('1')
  await trigger.click()
  await expect(page.getByLabel('Filter by priority')).toHaveValue('HIGH')
  await page.getByLabel('Filter by priority').selectOption('LOW')
  await expect(page).toHaveURL(/f.priority=LOW/)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
})
