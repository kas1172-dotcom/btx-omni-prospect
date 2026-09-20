import { expect, test } from '@playwright/test'

async function navigate(page, name) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name }).click()
}

test('desktop Today presents truthful priority, meaning, action, and evidence', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Today', level: 1 })).toBeVisible()
  const priorities = page.getByRole('region', { name: 'Top priorities' })
  await expect(priorities.locator('[data-summary-id]')).toHaveCount(3)
  await expect(page.getByLabel('Demonstration environment')).toHaveText('Simulated data environment')
  const attention = page.getByRole('heading', { name: 'Action priorities' }).locator('..').locator('..')
  await expect(attention).toContainText('Why:')
  await expect(attention).toContainText('Next:')
  await attention.getByRole('button', { name: 'Evidence and governed action' }).first().click()
  await expect(attention).toContainText('BTX commercial record')
  await page.getByRole('button', { name: 'Market watch and source coverage' }).click()
  await expect(page.getByRole('heading', { name: 'Public intelligence', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'View Intelligence' }).first().click()
  await expect(page.getByRole('heading', { name: 'Intelligence', level: 1 })).toBeVisible()

  await navigate(page, 'Today')
  const customer = page.locator('.today-attention-item .today-customer-link').first()
  const customerName = await customer.textContent()
  await customer.click()
  await expect(page.getByRole('heading', { name: customerName ?? '', level: 1 })).toBeVisible()
  await expect(page.locator('.today-surface')).toHaveCount(0)
})

test('Today consumes projected priority, market hubs, and curated IDs without substitution', async ({ page }) => {
  await page.goto('/')
  const payload = await page.evaluate(async () => (await fetch('/api/today')).json())
  const projectedPriority = payload.command_center.priority_briefing.map(item => item.id)
  const displayedPriority = projectedPriority.slice(0, 10)
  await expect(page.locator('[data-priority-id]')).toHaveCount(displayedPriority.length)
  expect(await page.locator('[data-priority-id]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-priority-id')))).toEqual(displayedPriority)
  await expect(page.locator('.today-lane-summary')).toContainText(`${projectedPriority.length} total action priorities`)

  const commercial = payload.command_center.priority_briefing.filter(item => item.kind === 'COMMERCIAL_REVIEW')
  const publicSignals = payload.command_center.priority_briefing.filter(item => item.kind === 'PUBLIC_SIGNAL')
  expect(await page.locator('[data-summary-id]').evaluateAll(nodes => nodes.map(node => node.getAttribute('data-summary-id')))).toEqual(projectedPriority.slice(0, 3))
  for (const item of commercial.filter(item => displayedPriority.includes(item.id))) {
    const card = page.locator(`[data-priority-id="${item.id}"]`)
    await card.getByRole('button', { name: 'Evidence and governed action' }).click()
    await expect(card).toContainText('BTX commercial record')
    await expect(card.getByRole('button', { name: 'Create action' })).toBeVisible()
  }
  for (const item of publicSignals.filter(item => displayedPriority.includes(item.id))) await expect(page.locator(`[data-priority-id="${item.id}"]`).getByRole('button', { name: 'Create action' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Market watch and source coverage' }).click()
  const defense = payload.command_center.market_hubs.find(hub => hub.market === 'Defense')
  await page.getByLabel('Watch market').selectOption('Defense')
  await expect(page.getByRole('heading', { name: 'Defense coverage and gaps' })).toBeVisible()
  const watchPanel = page.getByRole('heading', { name: 'Recommended Customer watchlist' }).locator('..').locator('..')
  const programPanel = page.getByRole('heading', { name: 'Watched programs' }).locator('..').locator('..')
  await expect(watchPanel.locator('.today-watch-list > button')).toHaveCount(Math.min(12, defense.watched_account_ids.length))
  await expect(programPanel.locator('.today-watch-list > button')).toHaveCount(defense.watched_program_ids.length)
  const coverage = page.getByRole('heading', { name: 'Defense coverage and gaps' }).locator('..').locator('..')
  for (const gap of defense.gaps) await expect(coverage).toContainText(gap)

  await page.getByLabel('Watch market').selectOption('')
  await expect(page.getByRole('heading', { name: 'Coverage and source freshness' })).toBeVisible()
  await expect(watchPanel.locator('.today-watch-list > button')).toHaveCount(Math.min(12, payload.command_center.watched_accounts.length))

  const intelligence = await page.evaluate(async () => (await fetch('/api/intelligence')).json())
  const projected = new Set(payload.command_center.curated_reference_signal_ids)
  const expectedCurated = intelligence.signals.filter(signal => projected.has(signal.id) && signal.data_mode === 'CURATED_PUBLIC')
  const curatedPanel = page.getByRole('heading', { name: 'Public intelligence', exact: true }).locator('..').locator('..')
  await expect(curatedPanel.locator('.seller-signal-brief')).toHaveCount(expectedCurated.length)
})

test('desktop Intelligence composes search and canonical filters with evidence and Omni selection', async ({ page }) => {
  await page.goto('/')
  await navigate(page, 'Intelligence')
  const search = page.getByRole('searchbox', { name: 'Search Intelligence' })
  await search.fill('Lockheed')
  await expect(page.locator('.intelligence-card')).toHaveCount(1)
  await expect(page.locator('.intelligence-card')).toContainText('Lockheed Martin')

  await page.getByLabel('Filter Intelligence by market').selectOption({ label: 'Defense' })
  await expect(page.locator('.intelligence-card')).toHaveCount(1)
  const active = page.getByLabel('Applied filters')
  await expect(active.getByRole('button', { name: 'Remove Market: Defense filter' })).toHaveAttribute('aria-pressed', 'true')
  await search.fill('no governed signal matches this')
  await expect(page.getByText(/No governed Intelligence matches/)).toBeVisible()
  await page.getByRole('button', { name: 'Clear all' }).click()
  await expect(page.locator('.intelligence-card').first()).toBeVisible()

  const signal = page.locator('.intelligence-card').first()
  const evidence = signal.getByRole('button', { name: /Evidence/ })
  await expect(evidence).toHaveAttribute('aria-expanded', 'false')
  await evidence.click()
  await expect(evidence).toHaveAttribute('aria-expanded', 'true')
  await expect(signal.locator('.ui-evidence')).toContainText('Source:')
  const useInOmni = signal.getByRole('button', { name: 'Use in Omni' })
  await useInOmni.click()
  await expect(signal.getByRole('button', { name: 'Clear Omni event' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeVisible()
})

test('public briefing joins the selected signal to canonical account context without cross-contaminating actions', async ({ page }) => {
  await page.goto('/')
  await navigate(page, 'Intelligence')
  const first = page.locator('.intelligence-card').first()
  const headline = await first.getByRole('heading').innerText()
  await first.getByRole('button', { name: 'Open briefing' }).click()

  await expect(page.locator('.intelligence-briefing h1')).toHaveText(headline)
  await expect(page).toHaveURL(/#\/intelligence\?view=brief&event=/)
  await expect(page.getByRole('heading', { name: 'Commercial relevance' })).toBeVisible()
  await page.getByRole('button', { name: /View supporting evidence/ }).click()
  await expect(page.getByRole('table', { name: 'Components and applicable business units' })).toBeVisible()
  await expect(page.getByText(/do not establish that this public event applies/)).toBeVisible()
  const next = page.getByRole('heading', { name: 'What should the seller do next?' }).locator('..')
  await expect(next).toContainText('Complete the account-specific assessment before deciding whether action is warranted.')
  await expect(next).not.toContainText('remaining bracket quantity')
  await expect(page.getByRole('complementary', { name: 'Briefing decisions and actions' })).toContainText('Signal Confidence')

  await page.reload()
  await expect(page.locator('.intelligence-briefing h1')).toHaveText(headline)
  await page.getByRole('button', { name: '← Back to Intelligence' }).click()
  await expect(page.getByRole('heading', { name: 'Intelligence', level: 1 })).toBeVisible()
})

test('public briefing exposes recoverable account-context failure and remains usable on mobile', async ({ page }) => {
  let allowSuccess = false
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (!allowSuccess && /^\/api\/accounts\/[^/]+\/?$/.test(path)) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary context failure' }) })
    } else await route.continue()
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button', { name: 'Intelligence' }).click()
  await page.locator('.intelligence-card').first().getByRole('button', { name: 'Open briefing' }).click()
  await expect(page.getByText('Customer context could not be loaded')).toBeVisible()
  allowSuccess = true
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByRole('heading', { name: 'Commercial relevance' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ask Omni about this signal' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})

test('mobile Today and Intelligence remain touch-usable at 390px and 320px without overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.locator('.today-priority-summary')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Action priorities' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
  await page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button', { name: 'Intelligence' }).click()
  await expect(page.getByRole('searchbox', { name: 'Search Intelligence' })).toBeVisible()
  await page.locator('.filter-mobile-trigger').click()
  await expect(page.getByLabel('Filter Intelligence by market')).toBeVisible()
  await expect(page.locator('.intelligence-card').first()).toBeVisible()
  await page.locator('.intelligence-card').first().getByRole('button', { name: /Evidence/ }).click()
  await expect(page.locator('.intelligence-card').first().locator('.ui-evidence')).toBeVisible()
  await expect(page.getByLabel('Open Omni assistant')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)

  await page.setViewportSize({ width: 320, height: 700 })
  await expect(page.getByRole('searchbox', { name: 'Search Intelligence' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
  await page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button', { name: 'Today' }).click()
  await expect(page.locator('.today-priority-summary')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})
