import { expect, test } from '@playwright/test'

test.use({ timezoneId: 'America/New_York' })

// A server contract response, not a client sorting fixture or the optional dev flag.
const canonical = [
  { id: 'public-stop', kind: 'PUBLIC_SIGNAL', triage_class: 0, high_importance: true, underlying_score: 5, hard_stop: true },
  { id: 'internal-risk', kind: 'COMMERCIAL_REVIEW', triage_class: 1, high_importance: true, underlying_score: 70 },
  { id: 'public-opportunity', kind: 'PUBLIC_SIGNAL', triage_class: 3, high_importance: true, underlying_score: 99 },
  { id: 'internal-standard', kind: 'COMMERCIAL_REVIEW', triage_class: 3, high_importance: false, severity: 'HIGH', underlying_score: 90 },
  { id: 'legacy', kind: 'COMMERCIAL_REVIEW', severity: 'HIGH' },
].map((row, index) => ({
  account_id: 'boeing', reason: `Decision ${row.id}`, recommended_action: 'Review governed evidence.',
  evidence_ids: [`evidence-${row.id}`], data_mode: 'SAMPLE', business_unit_ids: ['BU-TEST'],
  observed_at: `2026-09-${String(20 + index).padStart(2, '0')}T01:00:00Z`,
  triage_reason: `Server reason for ${row.id}`, ...row,
}))

async function installToday(page, { rows = canonical, allHubsEmpty = false } = {}) {
  await page.route('**/api/today', async route => {
    const response = await route.fetch()
    const body = await response.json()
    Object.assign(body.command_center, {
      priority_briefing: rows, action_priorities: rows.filter(row => row.kind === 'PUBLIC_SIGNAL'),
      needs_validation_assessments: [], current_signal_briefs: [], upcoming_radar: [],
      watched_accounts: [], watched_programs: [],
      market_hubs: ['Defense', 'Commercial Aerospace'].map((market, i) => ({ market,
        current_signal_ids: i === 0 && !allHubsEmpty ? ['public-stop'] : [], upcoming_signal_ids: [],
        watched_account_ids: [], watched_program_ids: [], source_ids: [], source_coverage: [], gaps: [] })),
    })
    await route.fulfill({ response, json: body })
  })
}

for (const width of [390, 1440]) {
  test(`canonical triage drives lead cards, count, badges and persistent rank at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.clock.setFixedTime(new Date('2026-09-20T13:00:00Z'))
    await installToday(page)
    await page.goto('/#/today')
    await expect(page.getByRole('heading', { level: 1, name: 'Good morning' })).toBeVisible()
    await expect(page.locator('.today-greeting')).toContainText('You have 3 high importance priorities.')
    const read = attribute => page.locator(`[${attribute}]`).evaluateAll((nodes, key) => nodes.map(node => node.getAttribute(key)), attribute)
    await expect.poll(() => read('data-priority-id')).toEqual(canonical.map(row => row.id))
    expect(await read('data-summary-id')).toEqual(canonical.slice(0, 3).map(row => row.id))
    await expect(page.locator('.today-priority-attention').getByText('High importance', { exact: true })).toHaveCount(3)
    await expect(page.locator('[data-summary-id][data-high-importance=true]')).toHaveCount(3)
    await expect(page.locator('[data-priority-id="legacy"]')).toContainText('Importance not yet determined')
    await expect(page.locator('[data-priority-id="internal-standard"]')).toContainText('Medium importance')
    await expect(page.locator('[data-priority-id="public-stop"] time')).toHaveText('Sample data as of Sep 19, 2026')
    await expect(page.locator('[data-priority-id="public-stop"] .today-rank')).toHaveAttribute('title', 'Server reason for public-stop')

    await page.getByLabel('Sort Today worklist').selectOption('RECENT')
    await expect.poll(() => read('data-priority-id')).toEqual([...canonical].reverse().map(row => row.id))
    await expect(page.locator('.today-rank')).toHaveText(['5', '4', '3', '2', '1'])
    await page.getByLabel('Search Today work').fill('internal-standard')
    await expect(page.locator('[data-priority-id]')).toHaveCount(1)
    await expect(page.locator('.today-rank')).toHaveText('4')
    expect(await read('data-summary-id')).toEqual(canonical.slice(0, 3).map(row => row.id))
    await expect(page.locator('.today-greeting')).toContainText('3 high importance priorities')
    const source = page.getByRole('group', { name: 'Priority source' })
    await expect(source.getByRole('button', { name: /^All/ })).toHaveText('All1')
    await expect(source.getByRole('button', { name: /^Public/ })).toHaveText('Public0')
    await expect(source.getByRole('button', { name: /^Internal/ })).toHaveText('Internal1')
    await source.getByRole('button', { name: /^Public/ }).click()
    await expect(page.locator('[data-priority-id]')).toHaveCount(0)
    await expect(source.getByRole('button', { name: /^Internal/ })).toHaveText('Internal1')
    // A filter-independent lead card must still open its canonical record.
    await page.locator('[data-summary-id="public-stop"]').getByRole('button', { name: 'Review priority' }).click()
    await expect(page.locator('[data-priority-id="public-stop"]')).toBeFocused()
    await expect(page.getByLabel('Search Today work')).toHaveValue('')
    await expect(page.getByLabel('Sort Today worklist')).toHaveValue('RANKED')
    await expect(page.locator('.today-rank')).toHaveText(['1', '2', '3', '4', '5'])
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
  })
}

test('Market Hubs keyboard tabs and selection survive URL reload, empty hubs cannot be selected', async ({ page }) => {
  await installToday(page)
  await page.goto('/#/today')
  await page.getByRole('tab', { name: 'Priorities', exact: true }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: 'Market Hubs' })).toBeFocused()
  await expect(page.getByRole('tab', { name: 'Market Hubs' })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('button', { name: /^Defense/ }).click()
  await expect(page).toHaveURL(/f.market=Defense/)
  const zeroHub = page.getByRole('button', { name: /^Commercial Aerospace/ })
  await expect(zeroHub).toBeDisabled()
  await expect(zeroHub).toHaveAttribute('title', 'No current or upcoming public signals')
  await expect(page.getByText('Counts show current and upcoming public signals.')).toBeVisible()
  await expect(page.getByText(/No watched accounts are available/)).toBeVisible()
  await expect(page.getByText(/No watched programs are available/)).toBeVisible()
  await page.reload()
  await expect(page.getByRole('tab', { name: 'Market Hubs' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('button', { name: /^Defense/ })).toHaveAttribute('aria-pressed', 'true')
})

test('all-empty hubs show a single hub empty notice and zero-priority header is honest', async ({ page }) => {
  await installToday(page, { rows: [], allHubsEmpty: true })
  await page.goto('/#/today')
  await expect(page.locator('.today-greeting')).toContainText('No high importance priorities right now.')
  await page.getByRole('tab', { name: 'Market Hubs' }).click()
  await expect(page.getByText('No current or upcoming public signals are available across Market Hubs.')).toHaveCount(1)
  await expect(page.getByRole('navigation', { name: 'Market hubs' })).toHaveCount(0)
})

test('one high importance item uses singular copy and date-only sample dates never shift', async ({ page }) => {
  await installToday(page, { rows: [{ ...canonical[0], observed_at: '2026-09-20' }] })
  await page.goto('/#/today')
  await expect(page.locator('.today-greeting')).toContainText('You have 1 high importance priority.')
  await expect(page.locator('[data-priority-id] time')).toHaveText('Sample data as of Sep 20, 2026')
})
