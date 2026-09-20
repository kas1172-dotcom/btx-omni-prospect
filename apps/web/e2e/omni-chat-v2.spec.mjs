import { expect, test } from '@playwright/test'

async function open(page) {
  await page.goto('/')
  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByRole('dialog', { name: 'Ask Omni', exact: true })).toBeVisible()
}

test('v2 scopes quote history, resumes after reload, and removes a deleted conversation', async ({ page }) => {
  await open(page)
  const stream = page.waitForResponse(r => r.url().endsWith('/api/omni/chat/stream'))
  await page.getByRole('textbox', { name: 'Ask Omni', exact: true }).fill('Does Lockheed Martin have quote history?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const response = await stream
  const event = (await response.text()).split('\n\n').find(x => x.startsWith('event: answer\n'))
  const result = JSON.parse(event.split('\ndata: ')[1])
  expect(result.response.account_id).toBe('lockheed-martin')
  await expect(page.locator('.message.assistant')).toContainText('Yes—Lockheed Martin')
  await expect(page.locator('.message.assistant')).toContainText('sample data')
  await page.reload()
  await page.getByLabel('Open Omni assistant').click()
  await page.getByRole('button', { name: 'Conversations', exact: true }).click()
  await page.getByRole('button', { name: 'Does Lockheed Martin have quote history?', exact: true }).last().click()
  await expect(page.locator('.message.assistant')).toContainText('Lockheed Martin')
  const removed = await page.request.delete('/api/omni/conversations/' + result.conversation_id)
  expect(removed.ok()).toBeTruthy()
  expect((await page.request.get('/api/omni/conversations/' + result.conversation_id)).status()).toBe(404)
  expect((await page.request.get('/api/omni/runs/' + result.response.run_id)).status()).toBe(404)
})

test('Action proposal opens reviewed existing form without saving', async ({ page }) => {
  await open(page)
  let writes = 0
  page.on('request', r => { if (r.url().endsWith('/api/actions') && r.method() === 'POST') writes++ })
  await page.getByRole('textbox', { name: 'Ask Omni', exact: true }).fill('Update Boeing in CRM and mark it won')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.message.assistant')).toContainText("I can't change CRM")
  await page.getByRole('button', { name: 'Propose an Action' }).click()
  const editor = page.getByRole('dialog', { name: 'Create Action', exact: true })
  await expect(editor).toBeVisible()
  await expect(editor.getByLabel('Title', { exact: true })).toHaveValue(/Boeing/)
  await editor.getByRole('button', { name: 'Cancel', exact: true }).click()
  expect(writes).toBe(0)
})

test('cancel aborts pending stream and markdown cannot execute HTML', async ({ page }) => {
  await page.route('**/api/omni/chat/stream', async route => {
    await new Promise(resolve => setTimeout(resolve, 1000))
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'event: done\ndata: {}\n\n' }).catch(() => {})
  })
  await open(page)
  await page.getByRole('textbox', { name: 'Ask Omni', exact: true }).fill('Hello')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Stopped')
  await page.unroute('**/api/omni/chat/stream')
  await page.route('**/api/omni/chat/stream', route => route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'event: answer\ndata: ' + JSON.stringify({ response: { content: '<img src=x onerror="window.chatUnsafe=true"> **Safe** [bad](javascript:alert(1))', account_id: '', citations: [], missingness: [], context_used: {}, provider_status: 'NOT_CONFIGURED' } }) + '\n\nevent: done\ndata: {}\n\n' }))
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.locator('.message.assistant strong')).toHaveText('Safe')
  expect(await page.locator('.message.assistant img').count()).toBe(0)
  expect(await page.locator('.message.assistant a[href^="javascript:"]').count()).toBe(0)
  expect(await page.evaluate(() => window.chatUnsafe)).toBeUndefined()
})
