import { expect, test } from '@playwright/test'
import { waitForToday } from './helpers.mjs'
import { readOmniAnswer } from './omni-stream-helpers.mjs'

test.describe.configure({ mode: 'serial' })

async function navigate(page, name) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name }).click()
  await expect(page.locator('.page-title h1')).toHaveText(name === 'Map' ? 'Tactical Map' : name === 'Profiles' ? 'Accounts' : name)
}

async function openOmni(page) {
  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeVisible()
}

async function ask(page, question) {
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/omni/chat/stream') && response.request().method() === 'POST')
  await page.locator('#omni-message').fill(question)
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  const body = await readOmniAnswer(response, page)
  const request = response.request().postDataJSON()
  await expect(page.locator('.message.assistant').last()).toContainText(body.content.slice(0, 48))
  return { request, body }
}

async function closeOmni(page) {
  await page.getByLabel('Close Omni').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeHidden()
}

async function expandTargetClusterIfPresent(page, target) {
  const cluster = page.getByRole('button', { name: new RegExp(`Cluster of .* Customers and Prospects:.*${target}`) }).first()
  if (await cluster.count()) await cluster.click()
}

test('Tactical Map composes canonical industry and SAMPLE commercial segment filters', async ({ page }) => {
  await waitForToday(page)
  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Filters' }).click()
  await page.getByRole('button', { name: 'Defense', exact: true }).click()
  await page.getByRole('button', { name: 'Customers', exact: true }).first().click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Lockheed Martin')
  await expect(page.getByRole('button', { name: 'Customer marker: Lockheed Martin', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Prospect marker: Anduril Industries' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Filters' }).click()
  await page.getByRole('button', { name: 'Prospects', exact: true }).first().click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Anduril Industries')
  const andurilMarker = page.getByRole('button', { name: 'Prospect marker: Anduril Industries · Anduril Industries headquarters', exact: true })
  await expect(andurilMarker).toBeVisible()
  await andurilMarker.click()
  await expect(page.getByRole('complementary', { name: 'Selected map location' })).toContainText('Anduril Industries')

  await page.getByRole('button', { name: 'Filters' }).click()
  await page.getByRole('button', { name: 'Customers', exact: true }).first().click()
  await page.getByRole('button', { name: 'Prospects', exact: true }).first().click()
  await page.getByRole('button', { name: 'Relationship needs review' }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expect(page.getByLabel('Active map filters').getByRole('button', { name: 'Remove Relationship needs review filter', exact: true })).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Selected map location' })).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Map site table', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Filters' }).click()
  await page.getByRole('dialog', { name: 'Filters' }).getByRole('button', { name: 'Reset filters' }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Anduril Industries')
  await expect(page.getByRole('button', { name: 'Prospect marker: Anduril Industries · Anduril Industries headquarters', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Filters' }).click()
  await page.getByRole('button', { name: 'Semiconductor', exact: true }).click()
  await page.getByRole('button', { name: 'Dormant customers' }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Applied Materials')
  const applied = page.getByRole('button', { name: 'Customer marker: Applied Materials', exact: true }).first()
  await expect(applied).toBeVisible()
  await page.getByRole('button', { name: 'Filters' }).click()
  await page.getByRole('dialog', { name: 'Filters' }).getByRole('button', { name: 'Reset filters' }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
})

test('Phase 7 seller scenarios remain coherent across real product surfaces', async ({ page }) => {
  test.setTimeout(120_000)
  const browserErrors = []
  page.on('pageerror', error => browserErrors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') browserErrors.push(message.text()) })
  const scenarioAccounts = [
    ['Southwest geographic trip planning', 'Anduril', 'anduril-industries'],
    ['Southwest geographic trip planning', 'Rocket Lab', 'rocket-lab-usa'],
    ['Southwest geographic trip planning', 'General Atomics', 'general-atomics'],
    ['Medical Device whitespace', 'Medtronic', 'medtronic'],
    ['Defense award and quote history', 'Lockheed', 'lockheed-martin'],
    ['Semiconductor expansion', 'Intel', 'intel'],
    ['Dormant customer reactivation', 'Applied Materials', 'applied-materials'],
    ['Quote follow-up', 'GE Aerospace', 'ge-aerospace'],
    ['Cross-BU conflict or overlap', 'Boeing', 'boeing'],
    ['Strong external signal with weak internal history', 'Intel', 'intel'],
    ['Strong internal history with weak external signal', 'Lam Research', 'lam-research'],
    ['Missing or unresolved evidence', 'Symbotic', 'symbotic'],
  ]

  await waitForToday(page)
  await openOmni(page)
  const today = await ask(page, 'What am I looking at?')
  expect(today.request.context.surface).toBe('TODAY')
  expect(today.body.context_used.status).toBe('DEGRADED')
  await closeOmni(page)

  // The full curated scenario roster is discoverable through the actual Accounts UI.
  await navigate(page, 'Profiles')
  await page.getByRole('button', { name: /^All \d/ }).click()
  const search = page.getByRole('searchbox', { name: 'Search Customers and Prospects' })
  for (const [scenario, account] of scenarioAccounts) {
    await search.fill(account)
    await expect(page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: new RegExp(account, 'i') }).first(), scenario).toBeVisible()
  }

  // Each canonical scenario anchor reaches Account 360 and Omni with the exact UI-selected ID.
  for (const [index, [, account, accountId]] of scenarioAccounts.entries()) {
    if (index === 0) {
      await search.fill(account)
      await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: new RegExp(account, 'i') }).first().click()
    } else {
      const switcher = page.getByLabel('Switch organization')
      await switcher.fill(account)
      await page.getByRole('option', { name: new RegExp(account, 'i') }).first().click()
    }
    await expect(page.getByRole('heading', { name: new RegExp(account, 'i'), level: 1 })).toBeVisible()
    await expect(page.locator('.account-workspace')).toBeVisible()
    await openOmni(page)
    const accountAnswer = await ask(page, 'Tell me about this account.')
    expect(accountAnswer.request.context.selected_account_id).toBe(accountId)
    expect(accountAnswer.body.account_id).toBe(accountId)
    await closeOmni(page)
  }

  // Defense award + quote-history scenario: Account Detail and Omni use the same exact ID.
  await navigate(page, 'Profiles')
  await search.fill('Lockheed')
  await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: /Lockheed/i }).first().click()
  await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
  await openOmni(page)
  const detail = await ask(page, 'Tell me about this account.')
  expect(detail.request.context.surface).toBe('ACCOUNT_DETAIL')
  expect(detail.request.context.selected_account_id).toBe('lockheed-martin')
  expect(detail.body.account_id).toBe('lockheed-martin')
  expect(detail.body.conversation_referent.account_id).toBe('lockheed-martin')
  const relationship = await ask(page, 'How are we connected to this company?')
  expect(relationship.body.account_id).toBe('lockheed-martin')
  const quotes = await ask(page, 'Which accounts have open quotes?')
  expect(quotes.body.context_used.account_id).toBeUndefined()
  expect(quotes.body.context_used.status).toBe('DEGRADED')
  expect(quotes.body.content).toContain("The AI service isn't available right now")
  await closeOmni(page)

  // Current Map contract exposes account markers; public facility layers are intentionally not rendered.
  await navigate(page, 'Map')
  await expect(page.locator('button[aria-label^="Public facility marker:"]')).toHaveCount(0)
  await expandTargetClusterIfPresent(page, 'Anduril Industries')
  const andurilMapMarker = page.getByRole('button', { name: 'Prospect marker: Anduril Industries · Anduril Industries headquarters', exact: true })
  await expect(andurilMapMarker).toBeVisible()
  await andurilMapMarker.click()
  await expect(page.getByRole('complementary', { name: 'Selected map location' })).toContainText('Anduril Industries')
  await openOmni(page)
  const accountMap = await ask(page, 'What account is selected on the map?')
  expect(accountMap.request.context.surface).toBe('MAP')
  expect(accountMap.request.context.selected_account_id).toBe('anduril-industries')
  expect(accountMap.request.context.selected_facility_id).toBe('public-hq-anduril-industries')
  await closeOmni(page)

  // A governed Suggestion converts to one durable Action; Omni remains read-only.
  await navigate(page, 'Actions')
  const actionPosts = []
  page.on('request', request => {
    if (request.method() === 'POST' && /\/api\/actions(?:\/|$)/.test(new URL(request.url()).pathname)) actionPosts.push(request.url())
  })
  await page.getByRole('button', { name: 'Suggested' }).click()
  const suggestionsRefresh = page.waitForResponse(response => response.url().endsWith('/api/actions') && response.request().method() === 'GET')
  await page.getByRole('button', { name: 'Refresh suggestions', exact: true }).click()
  await expect((await suggestionsRefresh).status()).toBe(200)
  const createSuggested = page.locator('.suggestion-detail').getByRole('button', { name: 'Create Action' })
  const suggestionRows = page.locator('[data-suggestion-id]')
  await expect(suggestionRows.first()).toBeVisible()
  for (let index = 0; index < await suggestionRows.count(); index += 1) {
    await suggestionRows.nth(index).click()
    if (await createSuggested.isVisible()) break
  }
  await expect(createSuggested).toBeVisible()
  await createSuggested.click()
  await expect(page.locator('.action-row.selected')).toBeVisible()
  const postsAfterUiCreation = actionPosts.length
  await openOmni(page)
  const action = await ask(page, 'Why was this created?')
  expect(action.request.context.surface).toBe('ACTIONS')
  expect(action.request.context.selected_action_id).toBeTruthy()
  expect(action.body.context_used.status).toBe('DEGRADED')
  expect(action.body.content).toMatch(/SAMPLE|sample|simulated/i)
  expect(actionPosts).toHaveLength(postsAfterUiCreation)
  await closeOmni(page)

  // A current filter is used only for the active view and disappears after the UI clears it.
  await navigate(page, 'Profiles')
  await page.getByLabel('Market', { exact: true }).selectOption('Defense')
  await openOmni(page)
  const filtered = await ask(page, 'What matters most on this page?')
  expect(filtered.request.context.active_filters.market).toBe('Defense')
  expect(filtered.body.context_used.status).toBe('DEGRADED')
  await closeOmni(page)
  await page.getByLabel('Market', { exact: true }).selectOption('ALL')
  await openOmni(page)
  const global = await ask(page, 'Which Defense accounts have the highest scores?')
  expect(global.request.context.active_filters?.market).toBeUndefined()
  expect(global.body.context_used.account_id).toBeUndefined()
  expect(global.body.context_used.filters?.market).toBeUndefined()
  expect(global.body.content).toContain("The AI service isn't available right now")
  await closeOmni(page)
  expect(browserErrors).toEqual([])
})
