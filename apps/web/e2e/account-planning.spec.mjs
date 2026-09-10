import { expect, test } from '@playwright/test'

async function openAccount(page, name) {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Customers & Prospects' }).click()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill(name)
  await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name, exact: true }).click()
  await expect(page.getByRole('heading', { name, level: 1 })).toBeVisible()
}

test('seller saves a dated private research shortlist and filters the same portfolio', async ({ page }) => {
  await openAccount(page, 'KLA Corporation')
  await expect(page.getByRole('heading', { name: 'Growth & research planning' })).toBeVisible()
  await page.getByRole('button', { name: 'Sales planning gap' }).click()
  const gap = page.getByText('No governed sales target is present, so a sales shortfall cannot be calculated.')
  await expect(gap).toBeVisible()
  await expect(page.getByText(/Governed target:/).locator('..')).toContainText('Unavailable')
  await page.getByLabel('Shortlist purpose').selectOption('RESEARCH')
  await page.getByLabel('Planning objective').fill('Confirm technical qualification and the correct buyer role.')
  await page.getByLabel('Target date').fill('2026-10-15')
  await page.getByRole('button', { name: 'Add to shortlist' }).click()
  await expect(page.getByText(/Saved for the signed-in user/)).toContainText('2026-10-15')

  await page.getByRole('button', { name: '← Customers & Prospects' }).click()
  await page.getByRole('button', { name: /Filters/ }).click()
  await page.getByRole('button', { name: 'My growth & research shortlist' }).click()
  await expect(page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('row')).toHaveCount(2)
  await expect(page.getByRole('table', { name: 'Customers and Prospects' })).toContainText('KLA Corporation')

  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  const savedPlanning = page.getByRole('group', { name: 'Saved account planning' })
  await savedPlanning.getByRole('button', { name: 'My growth & research shortlist' }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  const results = page.getByRole('region', { name: 'Map results' })
  await expect(results).toContainText('KLA Corporation')
  await expect(results).not.toContainText('Boeing')

  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Customers & Prospects' }).click()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('KLA Corporation')
  await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: 'KLA Corporation', exact: true }).click()
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
  await expect(page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('row')).toHaveCount(2)
  await expect(page.getByRole('table', { name: 'Customers and Prospects' })).toContainText('HUXWRX')
  await page.getByRole('button', { name: /Remove Only partnerships filter/ }).click()
  await page.getByRole('button', { name: 'Exclude partnerships' }).click()
  await expect(page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: 'HUXWRX', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: /Remove Exclude partnerships filter/ }).click()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('HUXWRX')
  await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: 'HUXWRX', exact: true }).click()
  await page.getByRole('button', { name: 'Manager designation' }).click()
  await page.getByLabel('Audited designation reason').fill('Manager review closed the temporary test classification.')
  await page.getByRole('button', { name: 'Remove strategic partnership' }).click()
  await expect(page.getByText('Strategic partnership designation')).toHaveCount(0)
})

test('a late planning read cannot overwrite a seller draft', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Customers & Prospects' }).click()
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('KLA Corporation')
  let releasePlanning
  const planningReleased = new Promise(resolve => { releasePlanning = resolve })
  await page.route('**/api/planning', async route => {
    if (route.request().method() !== 'GET') return route.continue()
    const response = await route.fetch()
    await planningReleased
    await route.fulfill({ response })
  })
  await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: 'KLA Corporation', exact: true }).click()
  const objective = 'Preserve this seller-authored qualification review.'
  await page.getByLabel('Planning objective').fill(objective)
  releasePlanning()
  await expect(page.getByRole('button', { name: 'Sales planning gap' })).toBeVisible()
  await expect(page.getByLabel('Planning objective')).toHaveValue(objective)
  await expect(page.getByRole('button', { name: 'Add to shortlist' })).toBeEnabled()
})
