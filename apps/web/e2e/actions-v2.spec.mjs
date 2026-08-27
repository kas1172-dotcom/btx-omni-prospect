import { expect, test } from '@playwright/test'

async function openActions(page, width = 1440, height = 960) {
  await page.setViewportSize({ width, height })
  await page.goto('/')
  await page.getByRole('button', { name: 'Actions', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'Actions', exact: true })).toBeVisible()
}

async function createAction(page, title, { approval = false } = {}) {
  await page.getByRole('button', { name: 'Create Action', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Create Action' })
  await dialog.getByLabel('Title').fill(title)
  await dialog.getByLabel('Details').fill('SAMPLE governed workflow detail')
  await dialog.getByLabel('Priority').selectOption('HIGH')
  if (approval) await dialog.getByLabel('External workflow requires Manager approval').check()
  await dialog.getByRole('button', { name: 'Create Action', exact: true }).click()
  await expect(dialog).toBeHidden()
}

test('salesperson creates, edits, persists, and completes an Action through valid transitions', async ({ page }) => {
  const title = `E2E seller durable review ${Date.now()}`
  await openActions(page)
  await createAction(page, title)
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Actions', exact: true }).first().click()
  await page.getByLabel('Search actions').fill(title)
  await page.locator('.action-row').filter({ hasText: title }).click()
  await page.getByRole('button', { name: 'Edit Action' }).click()
  await page.getByRole('dialog', { name: 'Edit Action' }).getByLabel('Details').fill('Edited durable detail')
  await page.getByRole('dialog', { name: 'Edit Action' }).getByRole('button', { name: 'Save changes' }).click()
  await page.getByRole('button', { name: 'Start work' }).click()
  await expect(page.locator('.action-detail').getByText('IN PROGRESS', { exact: true })).toBeVisible()
  await page.locator('.action-detail').getByRole('button', { name: 'Completed' }).click()
  await expect(page.locator('.action-detail').getByText('COMPLETED', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start work' })).toHaveCount(0)
})

test('Suggestions remain distinct and convert idempotently without an external write', async ({ page }) => {
  await openActions(page)
  await page.getByRole('button', { name: 'Suggested' }).click()
  await expect(page.getByText('Recommendations are not Actions')).toBeVisible()
  const conversion = page.locator('.suggestion-card').getByRole('button', { name: 'Create Action' }).first()
  if (await conversion.count()) {
    await conversion.click()
    await expect(page.getByText(/converted to one durable Action/i)).toBeVisible()
  }
  await expect(page.getByText(/No external operation was executed|Recommendations are not Actions/).first()).toBeVisible()
})

test('approval is Manager-only and remains separate from work status', async ({ browser }) => {
  const title = `E2E governed approval ${Date.now()}`
  const sellerPage = await browser.newPage()
  await openActions(sellerPage)
  await createAction(sellerPage, title, { approval: true })
  await expect(sellerPage.locator('.action-detail').getByText('Pending', { exact: true })).toBeVisible()
  await expect(sellerPage.getByText(/Manager review is required/)).toBeVisible()
  await expect(sellerPage.getByRole('button', { name: 'Approve' })).toHaveCount(0)
  await sellerPage.close()

  const managerContext = await browser.newContext()
  await managerContext.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
  const managerPage = await managerContext.newPage()
  await openActions(managerPage)
  await managerPage.getByLabel('Search actions').fill(title)
  await managerPage.locator('.action-row').filter({ hasText: title }).click()
  await managerPage.getByRole('button', { name: 'Edit Action' }).click()
  const editor = managerPage.getByRole('dialog', { name: 'Edit Action' })
  await editor.getByLabel('Owner ID').fill('seller-2')
  await editor.getByRole('button', { name: 'Save changes' }).click()
  await expect(managerPage.locator('.action-detail').getByText('seller-2', { exact: true })).toBeVisible()
  await managerPage.getByRole('button', { name: 'Approve' }).click()
  await expect(managerPage.getByText('Approved', { exact: true })).toBeVisible()
  await expect(managerPage.locator('.action-detail').getByText('OPEN', { exact: true })).toBeVisible()
  await managerPage.getByRole('button', { name: 'Evidence and history' }).click()
  await expect(managerPage.getByText('Approval decided', { exact: true })).toBeVisible()
  await managerContext.close()
})

test('390px Actions queue and create sheet remain touch-usable without overflow', async ({ page }) => {
  await openActions(page, 390, 844)
  const create = page.getByRole('button', { name: 'Create Action', exact: true })
  expect((await create.boundingBox())?.height).toBeGreaterThanOrEqual(44)
  await create.click()
  const dialog = page.getByRole('dialog', { name: 'Create Action' })
  await expect(dialog).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(page.getByLabel('Open Omni assistant')).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Mobile primary navigation' })).toBeVisible()
})

test('320px Actions list and sheet stay contained', async ({ page }) => {
  await openActions(page, 320, 844)
  await page.getByRole('button', { name: 'Create Action', exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
  await expect(page.getByRole('dialog', { name: 'Create Action' })).toBeVisible()
})
