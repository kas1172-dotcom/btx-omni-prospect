import { test, expect } from '@playwright/test'
import { selectSuggestion } from './helpers.mjs'

async function setVisibility(page, value) {
  if (page.viewportSize().width <= 760) {
    const trigger = page.getByLabel('Suggested filters').getByRole('button', { name: /^Filters/ })
    if (await trigger.getAttribute('aria-expanded') === 'false') await trigger.click()
  }
  await page.getByLabel('Visibility', { exact: true }).selectOption(value)
}

test('stale recommendation feedback is rejected without losing the draft; refresh requires review', async ({ page }) => {
  let stale = true
  await page.route('**/api/actions', async route => {
    if (route.request().method() !== 'GET') return route.continue()
    const response = await route.fetch()
    const data = await response.json()
    if (stale) data.suggestions = data.suggestions.map(item => ({ ...item, revision: '0'.repeat(64) }))
    await route.fulfill({ response, json: data })
  })
  await page.goto('/#/actions')
  const before = await (await page.request.get('/api/actions')).json()
  const suggestion = before.suggestions.find(item => !item.conversion_blocked)
  await page.getByRole('button', { name: /^Suggested \(\d+\)$/ }).click()
  await setVisibility(page, 'ALL')
  await page.getByRole('searchbox', { name: 'Search suggestions' }).fill(suggestion.title)
  const card = await selectSuggestion(page, suggestion.id)
  await card.getByRole('button', { name: /Give feedback|Edit my feedback/ }).click()
  await card.getByRole('combobox', { name: 'Feedback reason', exact: true }).selectOption('NOT_RELEVANT')
  const draft = `Retained stale review ${crypto.randomUUID()}`
  await card.getByLabel('Correction or completion source / optional note').fill(draft)
  await card.getByRole('button', { name: 'Save my feedback', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Recommendation evidence changed' })).toBeVisible()
  await expect(card.getByLabel('Correction or completion source / optional note')).toHaveValue(draft)
  const after = await (await page.request.get('/api/actions')).json()
  expect(after.items).toEqual(before.items)
  expect(after.suggestions.find(item => item.id === suggestion.id).feedback).toEqual(suggestion.feedback)
  stale = false
  await page.getByRole('button', { name: 'Refresh suggestions', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Suggestions refreshed' })).toBeVisible()
  await expect(card.getByLabel('Correction or completion source / optional note')).toHaveValue(draft)
  // Refresh does not automatically submit the retained draft.
  expect((await (await page.request.get('/api/actions')).json()).suggestions.find(item => item.id === suggestion.id).feedback).toEqual(suggestion.feedback)
})

for (const width of [390, 1440]) {
  test(`private feedback persists, keeps drafts, and can be undone at ${width}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('/#/actions')
    await page.getByRole('button', { name: /^Suggested \(\d+\)$/ }).click()
    await setVisibility(page, 'ALL')
    const row = page.locator('[data-suggestion-id]').filter({ hasText: 'Confirm fulfillment status and customer recovery plan.' }).first()
    await expect(row).toBeVisible()
    const id = await row.getAttribute('data-suggestion-id')
    const card = await selectSuggestion(page, id)
    const note = `Review request ${testInfo.testId}: account attribution requires source review`
    const edit = card.getByRole('button', { name: /^(Give feedback|Edit my feedback)$/ })
    await edit.click()
    await card.getByLabel('Feedback reason').selectOption('WRONG_ACCOUNT')
    await card.getByLabel('Correction or completion source / optional note').fill(note)
    await card.getByRole('button', { name: 'Close feedback' }).click()
    await edit.click()
    await expect(card.getByLabel('Correction or completion source / optional note')).toHaveValue(note)
    await card.getByRole('button', { name: 'Save my feedback' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Saved for you only' })).toBeVisible()
    await page.reload()
    await page.getByRole('button', { name: /^Suggested \(\d+\)$/ }).click()
    await setVisibility(page, 'HIDDEN')
    const persistedRow = page.locator(`[data-suggestion-id="${id}"]`)
    const persisted = await selectSuggestion(page, id)
    await expect(persisted).toContainText(note)
    await expect(persisted).toContainText('My feedback: Wrong account')
    await persisted.screenshot({ path: testInfo.outputPath(`feedback-${width}.png`) })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await persisted.getByRole('button', { name: 'Undo my feedback' }).click()
    await expect(persistedRow).toHaveCount(0)
    await setVisibility(page, 'ACTIVE')
    await selectSuggestion(page, id)
    await expect(page.locator('.suggestion-detail')).toContainText('My feedback: Restored')
    expect(errors).toEqual([])
  })
}

test('private feedback history inspects and reverses a persisted receipt without creating work', async ({ page }) => {
  await page.goto('/#/actions')
  const before = await (await page.request.get('/api/actions')).json()
  const suggestion = before.suggestions.find(item => !item.conversion_blocked)
  expect(suggestion.id).toMatch(/^suggestion-v2-/)
  const note = `History check ${crypto.randomUUID()}`
  const response = await page.request.post(`/api/actions/suggestions/${suggestion.id}/feedback`, { data: {
    reason: 'NOT_RELEVANT', note, expected_feedback_id: suggestion.feedback?.id ?? null, expected_revision: suggestion.revision, idempotency_key: crypto.randomUUID(),
  } })
  expect(response.ok()).toBe(true)
  await page.getByRole('button', { name: /^Suggested \(\d+\)$/ }).click()
  await page.getByText('My feedback history and earlier suggestions', { exact: true }).click()
  await page.getByRole('button', { name: 'Refresh my feedback history', exact: true }).click()
  const receipt = page.locator('.feedback-history-list li').filter({ hasText: note })
  await expect(receipt).toContainText('Stable canonical recommendation ID')
  await receipt.getByRole('button', { name: 'Undo this feedback', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Undo recorded for you' })).toBeVisible()
  await expect(receipt.getByRole('button', { name: 'Undo this feedback' })).toHaveCount(0)
  const after = await (await page.request.get('/api/actions')).json()
  expect(after.items).toEqual(before.items)
  expect(after.suggestions.find(item => item.id === suggestion.id).feedback.reason).toBe('UNDO')
})
