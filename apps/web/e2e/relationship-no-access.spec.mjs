import { test, expect } from '@playwright/test'
import { openRelationshipWorkspace } from './helpers.mjs'

test('documented-access absence retains canonical query metadata and recovers to shared experience', async ({ page }, testInfo) => {
  await page.goto('/#/accounts/kla')
  const section = await openRelationshipWorkspace(page)
  await expect(section.getByRole('combobox', { name: 'Objective', exact: true })).toBeVisible()
  const response = page.waitForResponse(r => r.url().endsWith('/api/relationships/query') && r.request().postDataJSON()?.mode === 'documented_access')
  await section.getByRole('combobox', { name: 'Objective', exact: true }).selectOption('documented_access')
  const result = await (await response).json()
  expect(result.search_complete).toBe(true)
  expect(result.examined_count).toBe(0)
  expect(result.scope.source_id).toBe('SAMPLE:account:kla')
  expect(result.scope.target_ids).toEqual([])
  expect(result.eligible_graph_revision).toBeTruthy()
  expect(result.rubric_version).toBe('BTX_RELATIONSHIP_POC_1')
  await expect(section.getByText('No documented person-to-person introduction is established.', { exact: true })).toBeVisible()
  await expect(section.getByRole('combobox', { name: 'Component scope', exact: true })).toBeVisible()
  await expect(section.getByRole('heading', { name: /Selected route/ })).toHaveCount(0)
  await section.getByRole('combobox', { name: 'Objective', exact: true }).selectOption('cross_account_experience')
  await expect(section.getByRole('heading', { name: /Selected route/ })).toBeVisible()
  await testInfo.attach('no-access-contract', { body: JSON.stringify(result, null, 2), contentType: 'application/json' })
})
