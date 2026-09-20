import { test, expect } from '@playwright/test'

for (const kind of ['communication', 'action']) {
  test(`${kind} editor waits for canonical accounts and retries a lost acknowledgement once`, async ({ page }) => {
    let release
    const gate = new Promise(resolve => { release = resolve })
    await page.route('**/api/accounts', async route => {
      const response = await route.fetch()
      await gate
      await route.fulfill({ response })
    })
    const apiPath = kind === 'communication' ? '/api/communications' : '/api/actions'
    let posts = 0
    let lost = false
    const submitted = []
    await page.route(`**${apiPath}`, async route => {
      if (route.request().method() !== 'POST') return route.continue()
      ++posts
      submitted.push(route.request().postDataJSON())
      const response = await route.fetch()
      if (!lost) { expect(response.ok()).toBeTruthy(); lost = true; await route.abort('failed') }
      else await route.fulfill({ response })
    })
    const title = `Independent ${kind} ${crypto.randomUUID()}`
    await page.goto(kind === 'communication' ? '/#/communications' : '/#/actions')
    await page.getByRole('button', { name: kind === 'communication' ? 'Create draft' : 'Create Action', exact: true }).click()
    const editor = page.getByRole('dialog', { name: kind === 'communication' ? 'Create communication' : 'Create Action', exact: true })
    await editor.getByLabel(kind === 'communication' ? 'Subject' : 'Title', { exact: true }).fill(title)
    await editor.getByLabel(kind === 'communication' ? 'Message' : 'Details', { exact: true }).fill('Private local review only. Do not send or promise capacity.')
    const save = editor.getByRole('button', { name: kind === 'communication' ? 'Save draft' : 'Create Action', exact: true })
    await expect(save).toBeDisabled()
    expect(posts).toBe(0)
    release()
    const customer = editor.getByRole('combobox', { name: 'Customer', exact: true })
    if (kind === 'communication') await customer.selectOption('boeing')
    else {
      await customer.fill('Boeing')
      await editor.getByRole('option', { name: /Boeing/ }).click()
      await expect(customer).toHaveValue('Boeing')
    }
    await save.click()
    await expect(editor).toContainText(/Failed to fetch|Load failed|fetch/i)
    await expect(editor.getByLabel(kind === 'communication' ? 'Subject' : 'Title', { exact: true })).toHaveValue(title)
    await save.click()
    await expect(editor).toBeHidden()
    expect(posts).toBe(2)
    expect(submitted[0].account_id).toBe('boeing')
    expect(submitted[0].idempotency_key).toBe(submitted[1].idempotency_key)
    const saved = await (await page.request.get(apiPath)).json()
    expect(saved.items.filter(item => (item.subject ?? item.title) === title)).toHaveLength(1)
  })
}
