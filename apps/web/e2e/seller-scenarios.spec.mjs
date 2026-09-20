import { expect, test } from '@playwright/test'
import { readOmniAnswer } from './omni-stream-helpers.mjs'

test.describe.configure({ mode: 'serial' })

async function navigate(page, name) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name }).click()
  if (name === 'Profiles') {
    const lists = page.getByRole('tablist', { name: 'Organization lists' })
    const back = page.getByRole('button', { name: '← Customers & Prospects' })
    await expect(lists.or(back)).toBeVisible()
    if (await back.isVisible()) await back.click()
    await expect(lists).toBeVisible()
  }
  else await expect(page.locator('.page-title h1')).toHaveText(name === 'Map' ? 'Tactical Map' : name)
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
  await page.goto('/')
  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await page.getByRole('button', { name: 'Defense', exact: true }).click()
  await page.getByRole('button', { name: 'Customers', exact: true }).first().click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Lockheed Martin')
  await expect(page.getByRole('button', { name: 'Customer marker: Lockheed Martin', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Prospect marker: Anduril Industries' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await page.getByRole('button', { name: 'Prospects', exact: true }).first().click()
  const markerLayers = page.locator('fieldset').filter({ hasText: 'Visible map layers' })
  await markerLayers.getByRole('button', { name: 'Public facilities', exact: true }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Anduril Industries')
  await expect(page.getByRole('button', { name: 'Prospect marker: Anduril Industries · Anduril Industries headquarters', exact: true })).toBeVisible()
  const anduril = page.getByRole('button', { name: 'Public facility marker: Anduril Industries headquarters' })
  await expect(anduril).toBeVisible()
  await anduril.click()
  await expect(anduril).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('heading', { name: 'Anduril Industries' })).toBeVisible()

  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await page.getByRole('button', { name: 'Customers', exact: true }).first().click()
  await page.getByRole('button', { name: 'Prospects', exact: true }).first().click()
  await page.getByRole('button', { name: 'Relationship needs review' }).click()
  for (const name of ['Customers', 'Prospects', 'Public facilities', 'BTX facilities', 'Intelligence']) await markerLayers.getByRole('button', { name, exact: true }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expect(page.getByText('No verified markers match the selected filters.')).toBeVisible()
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await page.getByRole('dialog', { name: 'Layers & filters' }).getByRole('button', { name: 'Reset filters' }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Anduril Industries')
  await expect(page.getByRole('button', { name: 'Prospect marker: Anduril Industries · Anduril Industries headquarters', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await page.getByRole('button', { name: 'Semiconductor', exact: true }).click()
  await page.getByRole('button', { name: 'Dormant customers' }).click()
  const customersLayer = markerLayers.getByRole('button', { name: 'Customers', exact: true })
  if (await customersLayer.getAttribute('aria-pressed') === 'false') await customersLayer.click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Applied Materials')
  const applied = page.getByRole('button', { name: 'Customer marker: Applied Materials', exact: true }).first()
  await expect(applied).toBeVisible()
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await page.getByRole('dialog', { name: 'Layers & filters' }).getByRole('button', { name: 'Reset filters' }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
})

test('Phase 7 seller scenarios remain coherent across real product surfaces', async ({ page }) => {
  test.setTimeout(120_000)
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

  await page.goto('/')
  await expect(page.locator('.page-title h1')).toHaveText('Today', { timeout: 15_000 })
  await openOmni(page)
  const today = await ask(page, 'What am I looking at?')
  expect(today.request.context.surface).toBe('TODAY')
  expect(today.body.context_used.status).toBe('DEGRADED')
  await closeOmni(page)

  // The full curated scenario roster is discoverable through the actual Accounts UI.
  await navigate(page, 'Profiles')
  await page.getByRole('button', { name: /Filters/ }).click()
  await page.getByLabel('Customer scope').selectOption('ALL')
  const catalog = (await (await page.request.get('/api/accounts')).json()).accounts
  const selectRoster = async id => {
    const relationship = catalog.find(account => account.id === id).relationship
    if (['CURRENT_CUSTOMER', 'FORMER_CUSTOMER'].includes(relationship)) await page.getByRole('tab', { name: 'Customers', exact: true }).click()
    else if (['TARGET', 'PROSPECT'].includes(relationship)) await page.getByRole('tab', { name: 'Prospects', exact: true }).click()
    else await page.getByRole('button', { name: /Needs classification/ }).click()
  }
  const search = page.getByPlaceholder('Search Customer, industry, or location')
  for (const [scenario, account, id] of scenarioAccounts) {
    await selectRoster(id)
    await search.fill(account)
    await expect(page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: new RegExp(account, 'i') }).first(), scenario).toBeVisible()
  }

  // Each canonical scenario anchor reaches Account 360 and Omni with the exact UI-selected ID.
  for (const [index, [, account, accountId]] of scenarioAccounts.entries()) {
    if (index === 0) {
      await selectRoster(accountId)
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
  await selectRoster('lockheed-martin')
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

  // A canonical Map facility is selected in the UI; no ownership is inferred from location.
  await navigate(page, 'Map')
  await page.getByRole('button', { name: 'Layers & filters' }).click()
  await expect(page.getByRole('dialog', { name: 'Layers & filters' })).toBeVisible()
  await page.locator('fieldset').filter({ hasText: 'Visible map layers' }).getByRole('button', { name: 'Public facilities', exact: true }).click()
  await page.getByRole('button', { name: 'Apply to map' }).click()
  await expandTargetClusterIfPresent(page, 'Anduril Industries')
  const andurilMarker = page.getByRole('button', {
    name: 'Public facility marker: Anduril Industries headquarters',
  })
  await expect(andurilMarker).toBeVisible()
  await andurilMarker.click()
  await expect(andurilMarker).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('heading', { name: 'Anduril Industries' })).toBeVisible()
  await openOmni(page)
  const facilityA = await ask(page, 'What does this facility do?')
  expect(facilityA.request.context.surface).toBe('MAP')
  expect(facilityA.request.context.selected_facility_id).toBeTruthy()
  expect(facilityA.body.context_used.status).toBe('DEGRADED')
  expect(facilityA.body.conversation_referent?.facility_id).toBeUndefined()
  await closeOmni(page)
  const secondFacility = page.locator('button[aria-label^="Public facility marker:"]').nth(1)
  await expect(secondFacility).toBeVisible()
  await secondFacility.click()
  await openOmni(page)
  const facilityB = await ask(page, 'Which account owns it?')
  expect(facilityB.request.context.selected_facility_id).toBeTruthy()
  expect(facilityB.request.context.selected_facility_id).not.toBe(facilityA.request.context.selected_facility_id)
  expect(facilityB.body.context_used.status).toBe('DEGRADED')
  await closeOmni(page)

  // A governed Suggestion converts to one durable Action; Omni remains read-only.
  await navigate(page, 'Actions')
  const actionPosts = []
  page.on('request', request => {
    if (request.method() === 'POST' && /\/api\/actions(?:\/|$)/.test(new URL(request.url()).pathname)) actionPosts.push(request.url())
  })
  await page.getByRole('button', { name: 'Suggested' }).click()
  const actionsResponse = await page.request.get('/api/actions')
  expect(actionsResponse.ok()).toBeTruthy()
  const actionsPayload = await actionsResponse.json()
  const convertible = actionsPayload.suggestions.find(item => !item.dismissed && !item.converted_action_id && !item.conversion_blocked)
  expect(convertible).toBeTruthy()
  await page.getByLabel('Search suggestions').fill(convertible.title)
  await page.locator(`[data-suggestion-id="${convertible.id}"]`).click()
  const createSuggested = page.locator('.suggestion-detail').getByRole('button', { name: 'Create Action' })
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
  await page.getByRole('button', { name: 'Defense', exact: true }).click()
  await openOmni(page)
  const filtered = await ask(page, 'What matters most on this page?')
  expect(filtered.request.context.active_filters.market).toBe('Defense')
  expect(filtered.body.context_used.status).toBe('DEGRADED')
  await closeOmni(page)
  await page.getByRole('button', { name: 'All industries', exact: true }).click()
  await openOmni(page)
  const global = await ask(page, 'Which Defense accounts have the highest scores?')
  expect(global.request.context.active_filters?.market).toBeUndefined()
  expect(global.body.context_used.account_id).toBeUndefined()
  expect(global.body.context_used.filters?.market).toBeUndefined()
  expect(global.body.content).toContain("The AI service isn't available right now")
  expect(global.body.context_used.status).toBe('DEGRADED')
  await closeOmni(page)
})
