import { expect, test } from '@playwright/test'

async function openAccount(page, name) {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Customers & Prospects' }).click()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill(name)
  await page.locator('.account-row').filter({ hasText: name }).first().click()
  await expect(page.getByRole('heading', { name, level: 1 })).toBeVisible()
}

test('seller saves a dated private research shortlist and filters the same portfolio', async ({ page }) => {
  await openAccount(page, 'KLA Corporation')
  await expect(page.getByRole('heading', { name: 'Growth & research planning' })).toBeVisible()
  await page.getByLabel('Shortlist purpose').selectOption('RESEARCH')
  await page.getByLabel('Planning objective').fill('Confirm technical qualification and the correct buyer role.')
  await page.getByLabel('Target date').fill('2026-10-15')
  await page.getByRole('button', { name: 'Add to shortlist' }).click()
  await expect(page.getByText(/Saved for the signed-in user/)).toContainText('2026-10-15')

  await page.getByRole('button', { name: '← Customers & Prospects' }).click()
  await page.getByRole('button', { name: /Filters/ }).click()
  await page.getByRole('button', { name: 'My growth & research shortlist' }).click()
  await expect(page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('row')).toHaveCount(2)
  await expect(page.locator('.account-row')).toContainText('KLA Corporation')

  await page.locator('.account-row').click()
  await page.getByRole('button', { name: 'Remove from shortlist' }).click()
  await expect(page.getByRole('button', { name: 'Add to shortlist' })).toBeVisible()
})

test('manager creates an audited partnership designation and portfolio include/exclude filters agree', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
  await openAccount(page, 'HUXWRX')
  await page.getByRole('button', { name: 'Manager designation' }).click()
  await page.getByLabel('Audited designation reason').fill('Manager-approved strategic account planning classification.')
  await page.getByRole('button', { name: 'Designate strategic partnership' }).click()
  await expect(page.getByText('Strategic partnership designation')).toBeVisible()

  await page.getByRole('button', { name: '← Customers & Prospects' }).click()
  await page.getByRole('button', { name: /Filters/ }).click()
  await page.getByRole('button', { name: 'Only partnerships' }).click()
  await expect(page.locator('.account-row')).toHaveCount(1)
  await expect(page.locator('.account-row')).toContainText('HUXWRX')
  await page.getByRole('button', { name: /Remove Only partnerships filter/ }).click()
  await page.getByRole('button', { name: 'Exclude partnerships' }).click()
  await expect(page.locator('.account-row').filter({ hasText: 'HUXWRX' })).toHaveCount(0)
  await page.getByRole('button', { name: /Remove Exclude partnerships filter/ }).click()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('HUXWRX')
  await page.locator('.account-row').filter({ hasText: 'HUXWRX' }).click()
  await page.getByRole('button', { name: 'Manager designation' }).click()
  await page.getByLabel('Audited designation reason').fill('Manager review closed the temporary test classification.')
  await page.getByRole('button', { name: 'Remove strategic partnership' }).click()
  await expect(page.getByText('Strategic partnership designation')).toHaveCount(0)
})
