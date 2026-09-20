import { expect, test } from '@playwright/test'
import { openCustomerSection, openRelationshipWorkspace } from './helpers.mjs'

async function inspectCanonicalNetwork(ranked) {
  await ranked.getByRole('combobox', { name: 'Objective', exact: true }).selectOption('commercial_fit')
  await expect(ranked).toHaveAttribute('aria-busy', 'false')
  const toggle = ranked.getByRole('button', { name: 'Explore network', exact: true })
  if (await toggle.isVisible()) await toggle.click()
  await expect(ranked.getByRole('group', { name: 'Canonical relationship network', exact: true })).toBeVisible()
  const selected = await ranked.getByRole('heading', { name: /Selected route/ }).textContent()
  await ranked.locator('foreignObject button').first().click()
  await expect(ranked).toContainText('Focused entity:')
  await expect(ranked.getByRole('heading', { name: /Selected route/ })).toHaveText(selected)
  await expect(ranked).toContainText('Next action:')
  await expect(ranked.locator('.relationship-graph-canvas')).toHaveCount(0)
}

async function openAccount(page, query) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Profiles' }).click()
  await expect(page.locator('.page-title h1')).toHaveText('Profiles')
  await page.getByPlaceholder('Search Customer, industry, or location').fill(query)
  await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: new RegExp(query, 'i') }).first().click()
  await expect(page.getByRole('heading', { name: new RegExp(query, 'i'), level: 1 })).toBeVisible()
}

test('Customer 360 presents canonical relationships in seller-facing language', async ({ page }) => {
  await page.goto('/')
  await openAccount(page, 'Lockheed')
  const relationshipResponse = page.waitForResponse(response => response.url().endsWith('/api/accounts/lockheed-martin/relationships?depth=2'))
  await openCustomerSection(page, /People and relationship paths/)
  const response = await relationshipResponse
  expect(response.status()).toBe(200)
  const lockheedRelationships = await response.json()
  expect(lockheedRelationships.account.id).toBe('lockheed-martin')
  expect(lockheedRelationships.direct_relationships.length).toBeGreaterThan(0)
  expect(lockheedRelationships.seller_direct_relationships.length).toBe(lockheedRelationships.direct_relationships.length)

  const relationshipPanel = page.locator('.account-workspace-relationship')
  await expect(relationshipPanel).toContainText('How this organization is connected')
  await expect(relationshipPanel).toContainText('Public professional contact research remains separate')
  await expect(relationshipPanel).toContainText(lockheedRelationships.seller_direct_relationships[0].steps.at(-1).display_name)
  await expect(relationshipPanel.locator('.seller-relationship-card').first()).toContainText('Connection:')
  await expect(relationshipPanel.locator('.seller-relationship-card').first()).toContainText('Why it matters:')
  await expect(relationshipPanel.locator('.seller-relationship-card').first()).toContainText('Suggested move:')
  await expect(relationshipPanel.getByRole('button', { name: /warm|intro/i })).toHaveCount(0)
  await expect(relationshipPanel).not.toContainText(/warm intro available|request intro|canonical 2-hop|PARENT_CHILD|SHARED_PROGRAM|Record:/)
  await expect(relationshipPanel).not.toContainText(/Strong|Moderate|Exploratory|High confidence/)

  const evidenceTrigger = relationshipPanel.locator('.seller-relationship-card').first().getByRole('button', { name: /Evidence/ })
  await evidenceTrigger.click()
  await expect(evidenceTrigger).toHaveAttribute('aria-expanded', 'true')
  await expect(relationshipPanel.locator('.seller-relationship-card').first().locator('.ui-evidence').first()).toBeVisible()
  await expect(relationshipPanel.locator('.seller-relationship-card').first().locator('.ui-evidence').first()).toContainText('Source reference:')

  const ranked = await openRelationshipWorkspace(page)
  await relationshipPanel.getByRole('tab', { name: 'Needs validation' }).click()
  await expect(relationshipPanel).toContainText(/No route requiring validation|Needs validation/)

  await inspectCanonicalNetwork(ranked)

  const switcher = page.getByLabel('Switch organization')
  await switcher.fill('Symbotic')
  await page.locator('.account-switch-result').filter({ hasText: 'Symbotic' }).click()
  await expect(page.locator('.account-workspace')).toContainText('Symbotic')
  const symboticResponse = page.waitForResponse(response => response.url().endsWith('/api/accounts/symbotic/relationships?depth=2'))
  await openCustomerSection(page, /People and relationship paths/)
  expect((await symboticResponse).status()).toBe(200)
  const symboticPanel = page.locator('.account-workspace-relationship')
  await expect(symboticPanel).toContainText('No eligible recorded route is currently available. This does not establish a real-world absence.')
  await expect(symboticPanel.locator('.seller-relationship-card')).toHaveCount(0)
  await expect(symboticPanel.locator('.ranked-route-steps')).toHaveCount(0)
  await expect(symboticPanel.locator('.relationship-graph-canvas')).toHaveCount(0)
})

test('mobile Relationship Intelligence uses readable vertical paths and disclosure', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await openAccount(page, 'Lockheed')

  const relationshipSection = page.locator('.account-workspace-relationship')
  await openCustomerSection(page, /People and relationship paths/)
  await openRelationshipWorkspace(page)
  await relationshipSection.getByRole('tab', { name: 'Recorded relationships' }).click()

  const firstPath = relationshipSection.locator('.seller-relationship-card').first()
  await expect(firstPath).toBeVisible()
  await expect(firstPath).toContainText('Why it matters:')
  const pathBox = await firstPath.boundingBox()
  expect(pathBox.width).toBeLessThanOrEqual(390)
  const evidenceTrigger = firstPath.getByRole('button', { name: /Evidence/ })
  await evidenceTrigger.click()
  await expect(evidenceTrigger).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByRole('button', { name: 'Open Omni assistant' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  await inspectCanonicalNetwork(page.getByRole('region', { name: 'Ranked canonical relationships', exact: true }))
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  const switcher = page.getByLabel('Switch organization')
  await switcher.fill('Symbotic')
  await page.locator('.account-switch-result').filter({ hasText: 'Symbotic' }).click()
  await expect(page.locator('.account-workspace')).toContainText('Symbotic')
  await page.getByRole('button', { name: /Profiles/ }).first().click()
  await expect(page.locator('.page-title h1')).toHaveText('Profiles')
})

test('Relationship Intelligence remains non-overflowing at 320px', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 })
  await page.goto('/')
  await openAccount(page, 'Lockheed')
  const relationshipSection = page.locator('.account-workspace-relationship')
  await openCustomerSection(page, /People and relationship paths/)
  const ranked = await openRelationshipWorkspace(page)
  await relationshipSection.getByRole('tab', { name: 'Recorded relationships' }).click()
  await expect(relationshipSection.locator('.seller-relationship-card').first()).toContainText('Connection:')
  await inspectCanonicalNetwork(ranked)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
