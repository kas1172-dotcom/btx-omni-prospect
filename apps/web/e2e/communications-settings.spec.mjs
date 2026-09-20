import { expect, test } from '@playwright/test'

async function openDesktop(page, destination) {
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: destination, exact: true }).click()
}

test('seller creates a durable governed draft without recipient or autonomous delivery', async ({ page }) => {
  const subject = `E2E governed communication ${Date.now()}`
  await openDesktop(page, 'Communications')
  await expect(page.getByRole('heading', { name: 'Communications', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Create draft' }).click()
  const editor = page.getByRole('dialog', { name: 'Create communication' })
  await editor.getByLabel('Subject').fill(subject)
  await editor.getByLabel('Message').fill('Human-reviewed SAMPLE outreach draft.')
  await expect(editor.getByText(/No verified deliverable email/)).toBeVisible()
  const createResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/communications' && response.request().method() === 'POST' && response.status() === 200)
  await editor.getByRole('button', { name: 'Save draft' }).click()
  await createResponse
  await expect(page.getByRole('heading', { name: subject })).toBeVisible()
  await expect(page.getByText('Delivery is not configured for this environment', { exact: true })).toBeVisible()
  await expect(page.getByText(/remains unsent and requires human review/i)).toBeVisible()
  await expect(page.getByText('Recipient unavailable').first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Approve', exact: true })).toHaveCount(0)
  await page.reload()
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Communications', exact: true }).click()
  await page.getByLabel('Search communications').fill(subject)
  await expect(page.getByText(subject).first()).toBeVisible()
})

test('manager can review but approval does not bypass recipient and confirmation boundaries', async ({ browser }) => {
  const subject = `E2E manager review ${Date.now()}`
  const seller = await browser.newPage()
  await openDesktop(seller, 'Communications')
  await seller.getByRole('button', { name: 'Create draft' }).click()
  const editor = seller.getByRole('dialog', { name: 'Create communication' })
  await editor.getByLabel('Subject').fill(subject)
  await editor.getByLabel('Message').fill('Governed review copy.')
  const createResponse = seller.waitForResponse(response => new URL(response.url()).pathname === '/api/communications' && response.request().method() === 'POST' && response.status() === 200)
  await editor.getByRole('button', { name: 'Save draft' }).click()
  await createResponse
  await seller.close()

  const context = await browser.newContext()
  await context.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
  const manager = await context.newPage()
  await openDesktop(manager, 'Communications')
  await manager.getByLabel('Search communications').fill(subject)
  await manager.locator('.communication-row').filter({ hasText: subject }).click()
  const approvalResponse = manager.waitForResponse(response => /\/api\/communications\/[^/]+\/approval$/.test(new URL(response.url()).pathname) && response.status() === 200)
  await manager.getByRole('button', { name: 'Approve', exact: true }).click()
  await approvalResponse
  await expect(manager.getByText(/approved by human review.*No message was sent/i)).toBeVisible()
  await expect(manager.getByText('Ready for delivery confirmation', { exact: true }).last()).toBeVisible()
  await expect(manager.getByRole('button', { name: 'Confirm send' })).toBeDisabled()
  await expect(manager.getByRole('region', { name: 'Audit history' })).toBeVisible()
  await expect(manager.getByText('Approved by reviewer', { exact: true }).last()).toBeVisible()
  await context.close()
})

test('Settings and secondary mobile navigation are role-aware, safe, and non-overflowing', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  const menu = page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button', { name: 'More', exact: true })
  await menu.click()
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible()
  await expect(page.getByText('Role & Access', { exact: true }).last()).toBeVisible()
  await expect(page.getByText(/cannot change or self-promote/)).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Settings sections' }).getByRole('link', { name: 'Integrations' })).toHaveCount(0)
  await expect(page.getByText('Communication delivery')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Source Health', exact: true })).toHaveCount(0)
  await expect(page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button')).toHaveText(['Today', 'Opportunities', 'Profiles', 'Intelligence', 'Map', 'Actions', 'More'])
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
  await page.setViewportSize({ width: 320, height: 700 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
  const body = await page.locator('body').innerText()
  expect(body).not.toMatch(/api[_ -]?key|access[_ -]?token|secret/i)
})

test('Settings failure stays on Settings and retries only its failed read', async ({ page }) => {
  let settingsRequests = 0
  let allowSuccess = false
  await page.route('**/*', async route => {
    if (!new URL(route.request().url()).pathname.startsWith('/api/settings')) {
      await route.continue()
      return
    }
    settingsRequests += 1
    // StrictMode may cancel the first transport before it reaches interception.
    // Keep failure active until the user explicitly retries this resource.
    if (!allowSuccess) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Unavailable"}' })
      return
    }
    await route.continue()
  })
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible()
  await expect(page.getByText('Settings could not be loaded')).toBeVisible()
  const failedRequests = settingsRequests
  expect(failedRequests).toBeGreaterThanOrEqual(1)
  await expect(page.getByRole('heading', { name: 'Today', exact: true })).toHaveCount(0)
  const retryResponse = page.waitForResponse(response => new URL(response.url()).pathname.startsWith('/api/settings') && response.status() === 200)
  allowSuccess = true
  await page.getByRole('button', { name: 'Retry Settings' }).click()
  await retryResponse
  await expect(page.getByText('Role & Access', { exact: true }).last()).toBeVisible()
  expect(settingsRequests).toBe(failedRequests + 1)
})
