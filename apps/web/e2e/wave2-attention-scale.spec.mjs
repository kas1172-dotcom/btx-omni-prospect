import { expect, test } from '@playwright/test'

const cloneAccount = (base, index) => ({ ...base, id: `scale-account-${index}`, name: `Scale Account ${String(index).padStart(3, '0')}`, legal_name: `Scale Account ${String(index).padStart(3, '0')} Incorporated`, domain: `scale-${index}.example`, industries: index % 2 ? ['Aerospace'] : ['Industrial'], relationship: index % 3 ? 'PROSPECT' : 'CURRENT_CUSTOMER' })

async function installScaleFixtures(page) {
  await page.route(/\/api\/accounts(?:\?.*)?$/, async route => {
    const response = await route.fetch(); const body = await response.json(); const base = body.accounts[0]
    body.accounts = [...body.accounts, ...Array.from({ length: 100 }, (_, index) => cloneAccount(base, index))]
    await route.fulfill({ response, json: body })
  })
  await page.route(/\/api\/today(?:\?.*)?$/, async route => {
    const response = await route.fetch(); const body = await response.json(); const base = body.command_center.priority_briefing[0]
    const priorities = Array.from({ length: 65 }, (_, index) => ({ ...base, id: `wave2-priority-${index}`, account_id: index % 2 ? 'boeing' : 'lockheed-martin', reason: `Decision reason ${String(index).padStart(2, '0')}`, recommended_action: `Governed family ${index % 5}: review decision ${index}`, evidence_ids: [`wave2-evidence-${index}`], observed_at: index % 11 === 0 ? undefined : `2026-08-${String((index % 28) + 1).padStart(2, '0')}T12:00:00Z`, signal_brief: undefined }))
    const validation = Array.from({ length: 17 }, (_, index) => ({ ...priorities[index], id: `wave2-validation-${index}`, outcome_lane: 'NEEDS_VALIDATION', kind: 'PUBLIC_SIGNAL', recommended_action: `Validate evidence ${index}` }))
    body.command_center.priority_briefing = priorities; body.command_center.action_priorities = priorities.filter(item => item.kind === 'PUBLIC_SIGNAL'); body.command_center.needs_validation_assessments = validation
    await route.fulfill({ response, json: body })
  })
  await page.route(/\/api\/actions(?:\?.*)?$/, async route => {
    if (route.request().method() !== 'GET') return route.continue()
    const response = await route.fetch(); const body = await response.json(); const actionBase = body.items[0] ?? { account_id: 'boeing', title: 'Review governed work', description: 'Fixture detail', owner_id: 'seller-1', priority: 'MEDIUM', status: 'OPEN', approval_status: 'NOT_REQUIRED', evidence_ids: [], context_referents: [], version: 1, created_by: 'seller-1', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' }
    body.items = Array.from({ length: 31 }, (_, index) => ({ ...actionBase, id: `wave2-action-${index}`, title: `Scale Action ${String(index).padStart(2, '0')}`, account_id: index % 2 ? 'boeing' : 'lockheed-martin', due_date: index % 7 === 0 ? undefined : `2026-10-${String((index % 28) + 1).padStart(2, '0')}`, priority: ['HIGH', 'MEDIUM', 'LOW'][index % 3] }))
    body.suggestions = Array.from({ length: 40 }, (_, index) => ({ id: `wave2-suggestion-${index}`, account_id: index % 2 ? 'boeing' : 'lockheed-martin', title: `Suggestion family ${index % 4}`, rationale: `Governed rationale ${index}`, priority: ['HIGH', 'MEDIUM', 'LOW'][index % 3], evidence_ids: [`suggestion-evidence-${index}`], source: 'SAMPLE_COMMERCIAL_ALERT', observed_at: `2026-09-${String((index % 16) + 1).padStart(2, '0')}T12:00:00Z`, dismissed: false, revision: String(index % 10).repeat(64), conversion_blocked: false }))
    await route.fulfill({ response, json: body })
  })
}

test('finite Today and scalable Actions retain every governed record through durable worklists', async ({ page }) => {
  await installScaleFixtures(page)
  await page.goto('/#/today')
  await expect(page.locator('.today-priority-card')).toHaveCount(3)
  await expect(page.locator('.today-lane-summary')).toContainText('65 total action priorities · 65 filtered · 10 displayed')
  await expect(page.locator('[data-priority-id]')).toHaveCount(10)
  await page.getByRole('navigation', { name: 'Worklist pages' }).first().getByRole('button', { name: 'Next' }).click()
  await expect(page).toHaveURL(/f\.page=2/)
  await expect(page.locator('[data-priority-id]')).toHaveCount(10)
  await page.getByLabel('Search Today work').fill('Decision reason 64')
  await expect(page.locator('.today-priority-card')).toHaveCount(1)
  await expect(page.locator('[data-priority-id]')).toHaveCount(1)

  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name: 'Actions' }).click()
  await expect(page.getByText('31 total Actions · 31 filtered · 12 displayed')).toBeVisible()
  await page.locator('.action-row').nth(3).click()
  await expect(page).toHaveURL(/action=wave2-action-/)
  await page.getByRole('navigation', { name: 'Worklist pages' }).getByRole('button', { name: 'Next' }).click()
  await expect(page).toHaveURL(/f\.page=2/)
  await page.reload()
  await expect(page.getByText('31 total Actions · 31 filtered · 12 displayed')).toBeVisible()

  await page.getByRole('button', { name: 'Suggested' }).click()
  await expect(page.getByText('40 total Suggestions · 40 filtered · 12 displayed')).toBeVisible()
  await expect(page.locator('[data-suggestion-id]')).toHaveCount(12)
  await page.locator('[data-suggestion-id]').nth(2).click()
  await expect(page).toHaveURL(/record=wave2-suggestion-/)
  await expect(page.locator('.suggestion-detail')).toContainText('Each canonical suggestion remains separate')
})

test('bounded account selector preserves canonical scope and mobile containment', async ({ page }) => {
  await installScaleFixtures(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/settings')
  const selector = page.getByRole('combobox', { name: 'Private memory scope' })
  await selector.fill('Scale Account 089')
  await expect(page.getByRole('option', { name: /Scale Account 089/ })).toHaveCount(1)
  await page.getByRole('option', { name: /Scale Account 089/ }).click()
  await expect(selector).toHaveValue('Scale Account 089')
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
  await selector.fill('organization that does not exist in this filter')
  await expect(page.getByText(/No choices match this filter/)).toBeVisible()
})

test('memory refresh keeps last-good content visible when only that resource fails', async ({ page }) => {
  let memoryReads = 0
  await page.route(/\/api\/omni\/memories(?:\?.*)?$/, async route => {
    if (route.request().method() !== 'GET') return route.continue()
    memoryReads += 1
    if (memoryReads > 1) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'fixture outage' }) })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [{
          id: 'wave2-memory-last-good',
          account_id: null,
          kind: 'WORK_PREFERENCE',
          content: 'Keep last-good preference visible',
          version: 1,
          expires_at: '2027-09-01T00:00:00Z',
          created_at: '2026-09-01T00:00:00Z',
          updated_at: '2026-09-01T00:00:00Z',
        }],
      }),
    })
  })

  await page.goto('/#/settings')
  await expect(page.getByText('Keep last-good preference visible')).toBeVisible()
  await page.getByRole('button', { name: 'Refresh memories' }).click()
  await expect(page.getByText('Keep last-good preference visible')).toBeVisible()
  await expect(page.getByText(/Refresh failed/)).toBeVisible()
})
