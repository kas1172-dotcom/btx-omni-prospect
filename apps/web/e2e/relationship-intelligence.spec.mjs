import { expect, test } from '@playwright/test'

async function openAccount(page, query, accountId) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Accounts' }).click()
  await expect(page.locator('.page-title h1')).toHaveText('Accounts')
  await page.getByPlaceholder('Search company, industry, or location').fill(query)
  const relationshipResponse = page.waitForResponse(response => response.url().endsWith(`/api/accounts/${accountId}/relationships?depth=2`))
  await page.locator('.account-row').filter({ hasText: query }).first().click()
  const response = await relationshipResponse
  expect(response.status()).toBe(200)
  return response.json()
}

test('Account 360 presents only canonical read-only Relationship Intelligence paths', async ({ page }) => {
  await page.goto('/')
  const lockheedRelationships = await openAccount(page, 'Lockheed', 'lockheed-martin')
  expect(lockheedRelationships.account.id).toBe('lockheed-martin')
  expect(lockheedRelationships.direct_relationships.length).toBeGreaterThan(0)

  const relationshipPanel = page.locator('.account-workspace-relationship')
  await expect(relationshipPanel.getByRole('heading', { name: 'Relationship Intelligence' })).toBeVisible()
  await expect(relationshipPanel).toContainText('Only canonical relationship records are shown.')
  await expect(relationshipPanel).toContainText('Public professional-contact research remains separate')
  await expect(relationshipPanel).toContainText(lockheedRelationships.direct_relationships[0].target_entity.name)
  await expect(relationshipPanel.getByRole('button')).toHaveCount(0)
  await expect(relationshipPanel).not.toContainText(/warm path|request intro/i)

  const switcher = page.getByLabel('Switch account')
  await switcher.fill('Symbotic')
  const symboticResponse = page.waitForResponse(response => response.url().endsWith('/api/accounts/symbotic/relationships?depth=2'))
  await page.locator('.account-switch-result').filter({ hasText: 'Symbotic' }).click()
  expect((await symboticResponse).status()).toBe(200)
  await expect(page.locator('.account-workspace')).toContainText('Symbotic')
  await expect(relationshipPanel).toContainText('Only canonical relationship records are shown.')
  await expect(relationshipPanel).toContainText('No canonical direct relationship records are available for this account.')
  await expect(relationshipPanel.locator('.relationship-path-row')).toHaveCount(0)
})
