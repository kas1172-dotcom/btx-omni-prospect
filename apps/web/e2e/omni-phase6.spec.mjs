import { expect, test } from '@playwright/test'

test.describe.configure({ mode: 'serial' })

async function openOmni(page) {
  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeVisible()
}

async function closeOmni(page) {
  await page.getByLabel('Close Omni').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeHidden()
}

async function ask(page, question) {
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/omni') && response.request().method() === 'POST')
  await page.locator('#omni-message').fill(question)
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  const body = await response.json()
  const request = response.request().postDataJSON()
  await expect(page.locator('.message.assistant').last()).toContainText(body.content.slice(0, 48))
  return { request, body }
}

async function navigate(page, name) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name }).click()
  await expect(page.locator('.page-title h1')).toHaveText(name)
}

test('Phase 6 Omni browser acceptance preserves typed context, continuity, and isolation', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.page-title h1')).toHaveText('Today')

  // Screen summary comes from the actual current UI context.
  await openOmni(page)
  const today = await ask(page, 'What am I looking at?')
  expect(today.request.context.surface).toBe('TODAY')
  expect(today.body.context_used.surface).toBe('TODAY')
  await closeOmni(page)

  // Select event A through the UI, then carry its typed referent into a follow-up.
  await navigate(page, 'Intelligence')
  await expect(page.getByRole('button', { name: 'Use in Omni' }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Use in Omni' }).first().click()
  await openOmni(page)
  const eventA = await ask(page, 'Why does this matter?')
  const eventAId = eventA.request.context.selected_event_id
  expect(eventAId).toBeTruthy()
  expect(eventA.body.context_used.event_id).toBe(eventAId)
  expect(eventA.body.conversation_referent.event_id).toBe(eventAId)
  await closeOmni(page)
  await page.getByRole('button', { name: 'Clear Omni event' }).click()
  await openOmni(page)
  const eventFollowUp = await ask(page, 'Which account is it tied to?')
  expect(eventFollowUp.request.context.selected_event_id).toBeUndefined()
  expect(eventFollowUp.request.context.conversation_referent.event_id).toBe(eventAId)
  expect(eventFollowUp.body.context_used.context_source).toBe('conversation')
  await closeOmni(page)

  // Select event B: a current same-type UI selection must supersede event A.
  await page.getByRole('button', { name: 'Use in Omni' }).nth(1).click()
  await openOmni(page)
  const eventB = await ask(page, 'Why is this important?')
  expect(eventB.request.context.selected_event_id).toBeTruthy()
  expect(eventB.request.context.selected_event_id).not.toBe(eventAId)
  expect(eventB.body.context_used.event_id).toBe(eventB.request.context.selected_event_id)
  expect(eventB.body.context_used.context_source).toBeUndefined()
  await closeOmni(page)

  // Leaving Intelligence clears its passive event selection before an Accounts summary.
  await navigate(page, 'Accounts')
  await openOmni(page)
  const cleared = await ask(page, 'Summarize this screen.')
  expect(cleared.request.context.selected_event_id).toBeUndefined()
  expect(cleared.body.context_used.surface).toBe('ACCOUNTS')
  await closeOmni(page)

  // A current market filter is serialized, then absent after clearing it.
  await page.getByRole('button', { name: 'Defense', exact: true }).click()
  await openOmni(page)
  const filtered = await ask(page, 'What matters most on this page?')
  expect(filtered.request.context.active_filters.market).toBe('Defense')
  expect(filtered.body.context_used.filters.market).toBe('Defense')
  await closeOmni(page)
  await page.getByRole('button', { name: 'All industries', exact: true }).click()
  await openOmni(page)
  const filterCleared = await ask(page, 'What matters most on this page?')
  expect(filterCleared.request.context.active_filters?.market).toBeUndefined()
  expect(filterCleared.body.context_used.filters?.market).toBeUndefined()

  // A global request does not inherit the event or a conversational entity as scope.
  const global = await ask(page, 'Which accounts have the highest attractiveness scores?')
  expect(global.request.context.selected_event_id).toBeUndefined()
  expect(global.request.context.conversation_referent).toBeUndefined()
  expect(global.body.context_used.event_id).toBeUndefined()
  expect(global.body.context_used.account_id).toBeUndefined()
})
