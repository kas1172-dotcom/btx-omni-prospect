import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/#/accounts')
  const access = page.getByLabel('Access code', { exact: true })
  await expect(access.or(page.getByRole('heading', { level: 1, name: 'Accounts', exact: true }))).toBeVisible()
  if (await access.isVisible()) {
    await access.fill('development-salesperson')
    await page.getByRole('button', { name: /Enter Project Beacon/ }).click()
  }
})

test('Relationships keeps ranked routes visible and the full graph secondary', async ({ page }) => {
  // The enhanced demo authors manufacturing routes on the fictional defense account.
  const accountId = process.env.E2E_RELATIONSHIP_ACCOUNT ?? 'boeing'
  await page.goto(`/#/accounts/${accountId}`)
  await page.getByRole('tab', { name: 'Relationships', exact: true }).click()
  const relationships = page.getByRole('region', { name: 'Ranked canonical relationships', exact: true })
  await expect(relationships).toHaveAttribute('aria-busy', 'false')
  await expect(relationships.locator('.ranked-route-cards').first()).toBeVisible()
  await expect(relationships).toContainText('Hypothetical')
  await expect(relationships).toContainText('Data Coverage')
  await expect(relationships.locator('.ranked-network')).toBeHidden()
  await relationships.getByRole('button', { name: 'Explore network', exact: true }).click()
  await expect(relationships.locator('.ranked-network')).toBeVisible()
  if (accountId !== 'boeing') {
    await page.goto('/#/accounts/boeing')
    await page.getByRole('tab', { name: 'Relationships', exact: true }).click()
  }
  await expect(page.getByRole('heading', { name: 'Contacts', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Research', exact: true }).first()).toBeVisible()
})

test('Boeing commercial line reconciles and uses governed follow-up preview', async ({ page }) => {
  await page.goto('/#/accounts/boeing')
  await expect(page.getByRole('heading', { level: 1, name: 'Boeing', exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Commercial', exact: true }).click()
  const panel = page.locator('.profile-commercial')
  await expect(panel.getByRole('heading', { name: 'Orders', exact: true })).toBeVisible()
  const detail = await (await page.request.get('/api/accounts/boeing')).json()
  const line = detail.profile.fulfillment.lines.find(row => row.ordered_quantity === 292)
  expect(line).toBeTruthy()
  const order = panel.getByRole('row').filter({ has: page.getByRole('button', { name: line.order_id, exact: true }) })
  await expect(order).toContainText('292')
  await expect(order).toContainText('146')
  await expect(order).toContainText('$143,080')
  await order.getByRole('button').click()
  await expect(panel.getByRole('heading', { name: 'Lines, shipments & cancellations' })).toBeVisible()
  await panel.getByRole('button', { name: 'Preview local follow-up', exact: true }).first().click()
  await expect(panel.getByRole('region', { name: 'Local follow-up preview' })).toBeVisible()
  await expect(panel.getByRole('region', { name: 'Local follow-up preview' })).toContainText('No external')
})

test('account views persist, filter canonical rows and support keyboard navigation', async ({ page }) => {
  await page.goto('/#/accounts')
  const table = page.getByRole('table', { name: 'Customers and Prospects', exact: true })
  await expect(table).toBeVisible()
  await expect(table.getByRole('columnheader', { name: 'Priority', exact: true })).toHaveCount(0)
  await expect(table.getByRole('columnheader', { name: 'Evidence', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: /^Customers \d/ }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: /^Customers \d/ })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('Boeing')
  const row = table.locator(':scope > tbody > tr')
  await expect(row).toHaveCount(1)
  await expect(row).toContainText('Data Coverage')
  await expect(row).toContainText('public')
  await expect(row).toContainText('internal')
  await row.focus()
  await row.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: 'Boeing', exact: true })).toBeVisible()
})

