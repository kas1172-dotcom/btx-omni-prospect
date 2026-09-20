import { expect, test } from '@playwright/test'

test('a stale autosave retains the typed value and retries only after explicit revision reload', async ({ page }) => {
  const title = `Conflict ${crypto.randomUUID()}`
  const created = await (await page.request.post('/api/actions', { data: { title } })).json()
  await page.goto(`/#/actions?action=${created.id}`)
  const input = page.locator('.action-detail').getByLabel('Title', { exact: true })
  await expect(input).toHaveValue(title)
  const external = await page.request.patch(`/api/actions/${created.id}`, { data: { title: 'Concurrent version', expected_version: created.version } })
  expect(external.ok()).toBeTruthy()
  await input.fill('My retained task title')
  await input.blur()
  await expect(page.getByText(/Your typed value is retained/)).toBeVisible()
  await expect(input).toHaveValue('My retained task title')
  expect((await (await page.request.get(`/api/actions/${created.id}`)).json()).title).toBe('Concurrent version')
  await page.getByRole('button', { name: 'Reload revision and retry Title' }).click()
  await expect.poll(async () => (await (await page.request.get(`/api/actions/${created.id}`)).json()).title).toBe('My retained task title')
})

test('failed history is an explicit retryable error, not empty activity', async ({ page }) => {
  const created = await (await page.request.post('/api/actions', { data: { title: `History ${crypto.randomUUID()}` } })).json()
  const url = `**/api/actions/${created.id}/history`
  await page.route(url, route => route.abort('failed'))
  await page.goto(`/#/actions?action=${created.id}`)
  await page.getByRole('button', { name: 'Evidence and history' }).click()
  await expect(page.getByText(/Action history could not be loaded/)).toBeVisible()
  await page.unroute(url)
  await page.getByRole('button', { name: 'Retry history' }).click()
  await expect(page.getByRole('list', { name: 'Action history' })).toContainText('CREATED')
})

test('a stale customer selection stays available until explicit retry', async ({ page }) => {
  const created = await (await page.request.post('/api/actions', { data: { title: `Customer conflict ${crypto.randomUUID()}` } })).json()
  await page.goto(`/#/actions?action=${created.id}`)
  const detail = page.locator('.action-detail')
  await expect(detail.getByLabel('Title', { exact: true })).toHaveValue(created.title)
  const external = await page.request.patch(`/api/actions/${created.id}`, { data: { description: 'Concurrent edit', expected_version: created.version } })
  expect(external.ok()).toBeTruthy()
  const customer = detail.getByRole('combobox', { name: 'Customer', exact: true })
  await customer.fill('Boeing')
  await detail.getByRole('option', { name: /Boeing/ }).click()
  await expect(detail.getByRole('button', { name: 'Reload revision and retry Customer' })).toBeVisible()
  await expect(customer).toHaveValue('Boeing')
  expect((await (await page.request.get(`/api/actions/${created.id}`)).json()).account_id).toBeNull()
  await detail.getByRole('button', { name: 'Reload revision and retry Customer' }).click()
  await expect.poll(async () => (await (await page.request.get(`/api/actions/${created.id}`)).json()).account_id).toBe('boeing')
})

test('Customer 360 creates a task that appears in Actions with its source link', async ({ page }) => {
  const title = `Customer follow-up ${crypto.randomUUID()}`
  await page.goto('/#/accounts/boeing')
  await page.locator('.account-detail-surface').getByRole('button', { name: /^Actions/ }).click()
  await page.getByLabel('Create internal Action').fill(title)
  await page.getByRole('button', { name: 'Create Action', exact: true }).click()
  await expect(page.getByText('Internal Action created. No external system was changed.')).toBeVisible()
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Actions', exact: true }).click()
  await page.getByLabel('Search actions').fill(title)
  await page.locator('.action-select').filter({ hasText: title }).click()
  await expect(page.locator('.action-detail').getByRole('link', { name: 'Customer 360', exact: true })).toHaveAttribute('href', '#/accounts/boeing')
})
