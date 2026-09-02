import { expect, test } from '@playwright/test'

async function openAccount(page, query, accountId) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Customers & Prospects' }).click()
  await expect(page.locator('.page-title h1')).toHaveText('Customers & Prospects')
  await page.getByPlaceholder('Search Customer, industry, or location').fill(query)
  const mobile = page.viewportSize().width <= 760
  const relationshipResponse = mobile ? undefined : page.waitForResponse(response => response.url().endsWith(`/api/accounts/${accountId}/relationships?depth=2`))
  const customerRow = mobile ? page.locator('.portfolio-mobile-list .ui-mobile-row') : page.locator('.account-row')
  await customerRow.filter({ hasText: query }).first().click()
  if (!relationshipResponse) {
    await expect(page.locator('.account-workspace')).toBeVisible()
    return undefined
  }
  const response = await relationshipResponse
  expect(response.status()).toBe(200)
  return response.json()
}

test('Customer 360 presents canonical relationships in seller-facing language', async ({ page }) => {
  await page.goto('/')
  const lockheedRelationships = await openAccount(page, 'Lockheed', 'lockheed-martin')
  expect(lockheedRelationships.account.id).toBe('lockheed-martin')
  expect(lockheedRelationships.direct_relationships.length).toBeGreaterThan(0)
  expect(lockheedRelationships.seller_direct_relationships.length).toBe(lockheedRelationships.direct_relationships.length)

  const relationshipPanel = page.locator('.account-workspace-relationship')
  await expect(relationshipPanel.getByRole('heading', { name: 'Relationship Intelligence' })).toBeVisible()
  await expect(relationshipPanel).toContainText('How this Customer is connected')
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

  await relationshipPanel.getByRole('tab', { name: 'Connections to review' }).click()
  await expect(relationshipPanel).toContainText('No connection requiring validation is currently available for this Customer.')

  await relationshipPanel.getByRole('tab', { name: 'Graph view' }).click()
  await expect(relationshipPanel.getByRole('group', { name: 'Governed relationship graph' })).toBeVisible()
  await expect(relationshipPanel.getByLabel('Relationship graph legend')).toContainText('Validated')
  const graphNode = relationshipPanel.locator('.relationship-graph-node').first()
  await graphNode.click()
  await expect(relationshipPanel.locator('.relationship-graph-detail')).toContainText('Selected context')
  await expect(relationshipPanel.locator('.relationship-graph-detail')).toContainText('Why it matters:')
  await expect(relationshipPanel.locator('.relationship-graph-detail')).not.toContainText(/warm intro available|confidence|strength percentage/i)

  const switcher = page.getByLabel('Switch Customer')
  await switcher.fill('Symbotic')
  const symboticResponse = page.waitForResponse(response => response.url().endsWith('/api/accounts/symbotic/relationships?depth=2'))
  await page.locator('.account-switch-result').filter({ hasText: 'Symbotic' }).click()
  expect((await symboticResponse).status()).toBe(200)
  await expect(page.locator('.account-workspace')).toContainText('Symbotic')
  await relationshipPanel.getByRole('tab', { name: 'Validated connections' }).click()
  await expect(relationshipPanel).toContainText('No eligible validated connection is currently available for this Customer. This does not establish a real-world absence.')
  await expect(relationshipPanel.locator('.seller-relationship-card')).toHaveCount(0)
  await relationshipPanel.getByRole('tab', { name: 'Graph view' }).click()
  await expect(relationshipPanel).toContainText('No eligible governed relationship path is available to visualize.')
})

test('mobile Relationship Intelligence uses readable vertical paths and disclosure', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await openAccount(page, 'Lockheed', 'lockheed-martin')

  const relationshipSection = page.locator('.account-workspace-relationship')
  const sectionTrigger = relationshipSection.getByRole('button', { name: /Relationship Intelligence/ })
  await sectionTrigger.click()
  await expect(sectionTrigger).toHaveAttribute('aria-expanded', 'true')
  await relationshipSection.getByRole('tab', { name: 'Validated connections' }).click()

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

  await relationshipSection.getByRole('tab', { name: 'Graph view' }).click()
  await expect(relationshipSection.getByRole('group', { name: 'Governed relationship graph' })).toBeVisible()
  await relationshipSection.locator('.relationship-graph-node').first().click()
  await expect(relationshipSection.locator('.relationship-graph-detail')).toContainText('Selected context')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

  const switcher = page.getByLabel('Switch Customer')
  await switcher.fill('Symbotic')
  await page.locator('.account-switch-result').filter({ hasText: 'Symbotic' }).click()
  await expect(page.locator('.account-workspace')).toContainText('Symbotic')
  await page.getByRole('button', { name: /Customers & Prospects/ }).first().click()
  await expect(page.locator('.page-title h1')).toHaveText('Customers & Prospects')
})

test('Relationship Intelligence remains non-overflowing at 320px', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 })
  await page.goto('/')
  await openAccount(page, 'Lockheed', 'lockheed-martin')
  const relationshipSection = page.locator('.account-workspace-relationship')
  await relationshipSection.getByRole('button', { name: /Relationship Intelligence/ }).click()
  await relationshipSection.getByRole('tab', { name: 'Validated connections' }).click()
  await expect(relationshipSection.locator('.seller-relationship-card').first()).toContainText('Connection:')
  await relationshipSection.getByRole('tab', { name: 'Graph view' }).click()
  await expect(relationshipSection.getByRole('group', { name: 'Governed relationship graph' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})
