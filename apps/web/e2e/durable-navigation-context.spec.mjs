import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 1440, height: 900 } })

const accountId = 'lockheed-martin'
const eventId = 'navigation-event'
const assessmentId = 'navigation-assessment'
const assessmentVersion = 7

const briefing = {
  id: eventId,
  context_id: `${eventId}:${accountId}`,
  assessment_id: assessmentId,
  assessment_version: assessmentVersion,
  canonical_account_ids: [accountId],
  canonical_program_id: 'program-navigation',
  headline: 'Reviewed navigation assessment',
  seller_summary: 'A governed signal may warrant a scoped review.',
  what_happened: 'A source-backed program change was announced.',
  why_it_may_matter: 'Existing account history may help BTX validate adjacent work without establishing program participation.',
  what_to_watch: 'Confirm program, component, facility and buyer scope.',
  recommended_action: 'Review the cited notice and related quote before proposing pursuit work.',
  action_rationale: 'The customer relationship is established; participation in the new program is not.',
  material_uncertainties: ['BTX participation in the announced program is not established.'],
  markets: ['Defense'],
  event_timing: 'RECENT', freshness: 'CURRENT', data_mode: 'LIVE_PUBLIC', analysis_status: 'READY',
  commercial_relevance_state: 'ESTABLISHED_ACCOUNT_REVIEW', priority_eligible: true, summary_mode: 'DETERMINISTIC',
  publication_timestamp: '2026-09-01T00:00:00Z', source_system: 'Official program source',
  source_url: 'https://example.com/program', resolution_state: 'RESOLVED_ELIGIBLE', seller_promotion_state: 'ELIGIBLE',
  evidence_ids: ['public-program-source'], references: [{ evidence_id: 'public-program-source', title: 'Official program source', url: 'https://example.com/program', publication_date: '2026-09-01' }],
  priority_reasons: [], missing_fields: [],
  evidence_package: { commercial_record_scope: 'EXACT_PROGRAM', commercial_records: [{ collection: 'quotes', record_id: 'QUO2-LOCKHEED-AGR1', date: '2025-07-15', display_name: 'Lockheed agreement quote', match_reasons: ['Shares the governed customer and program scope'], match_strength: 'Strong scoped match', unknowns: 'Technical qualification remains unconfirmed.', validation_action: 'Inspect the quote and confirm program scope.', status: 'WON', value_minor: 152640000, currency: 'USD' }] },
}

async function installAssessmentFixture(page) {
  const accountResponse = await page.request.get(`/api/accounts/${accountId}`)
  const account = await accountResponse.json()
  account.customer_360.intelligence = [{ id: eventId, business_briefing: briefing }, ...account.customer_360.intelligence]
  await page.route(/\/api\/today(?:\?.*)?$/, async route => {
    const response = await route.fetch(); const body = await response.json()
    const item = { id: 'priority-navigation', kind: 'PUBLIC_SIGNAL', account_id: accountId, severity: 'MEDIUM', reason: briefing.why_it_may_matter, recommended_action: briefing.recommended_action, evidence_ids: briefing.evidence_ids, observed_at: briefing.publication_timestamp, data_mode: 'LIVE_PUBLIC', business_unit_ids: ['chandler-industries'], event_id: eventId, signal_brief: briefing }
    body.command_center.priority_briefing = [item, ...body.command_center.priority_briefing]
    body.command_center.current_signal_briefs = [briefing, ...body.command_center.current_signal_briefs]
    await route.fulfill({ response, json: body })
  })
  await page.route(`**/api/accounts/${accountId}`, route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(account) }))
}

async function openSelectedAssessmentFromToday(page) {
  await installAssessmentFixture(page)
  await page.goto('/#/today')
  await page.getByRole('button', { name: 'Public intelligence' }).click()
  const priority = page.locator('[data-priority-id="priority-navigation"]')
  await priority.getByText('Evidence and governed action').click()
  await priority.getByRole('button', { name: 'Use in Omni' }).click()
  await priority.locator('.seller-signal-brief').getByRole('button', { name: 'Lockheed Martin' }).click()
  await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
}

test('Today assessment and related record retain the filtered return location through browser history', async ({ page }) => {
  await openSelectedAssessmentFromToday(page)
  expect(page.url()).toContain(`assessment=${assessmentId}`)
  expect(page.url()).toContain('return=%23%2Ftoday')
  const related = page.locator('.account-primary-grid .customer-section').filter({ hasText: 'Related BTX activity to review' })
  await related.getByRole('button', { name: /Related BTX activity to review/ }).click()
  await related.getByRole('button', { name: 'Inspect source record' }).first().click()
  await expect(page.getByRole('region', { name: 'Lockheed agreement quote source record' })).toBeVisible()
  expect(page.url()).toContain('view=record')
  await page.goBack(); await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
  await page.goBack(); await expect(page.getByRole('heading', { name: 'Today', level: 1 })).toBeVisible()
  expect(page.url()).toContain('f.kind=PUBLIC_SIGNAL')
  expect(page.url()).toContain(`assessment=${assessmentId}`)
  await expect(page.locator('[data-priority-id="priority-navigation"]')).toBeVisible()
})

test('Intelligence briefing to Organization 360 refresh restores the exact assessment version', async ({ page }) => {
  await installAssessmentFixture(page)
  await page.goto('/#/intelligence?f.customer=lockheed-martin&sort=MOST_RECENT')
  const card = page.locator('.intelligence-card').filter({ hasText: briefing.headline }).first()
  await card.getByRole('button', { name: 'Open briefing' }).click()
  await page.getByRole('button', { name: 'Open full profile' }).click()
  await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
  const before = page.url()
  expect(before).toContain(`assessment=${assessmentId}`); expect(before).toContain(`av=${assessmentVersion}`)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
  expect(page.url()).toBe(before)
  await expect(page.getByRole('heading', { name: briefing.headline }).first()).toBeVisible()
})

test('Map facility scope survives Organization 360 and is supplied when Omni opens', async ({ page }) => {
  await page.goto('/#/map?account_id=lockheed-martin&facility=public-hq-lockheed-martin&scope=facility')
  await expect(page.getByRole('heading', { name: 'Lockheed Martin' }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Open Organization 360' }).click()
  await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
  expect(page.url()).toContain('facility=public-hq-lockheed-martin'); expect(page.url()).toContain('scope=facility')
  await page.getByLabel('Open Omni assistant').click()
  const request = page.waitForRequest(item => item.url().endsWith('/api/omni') && item.method() === 'POST')
  await page.getByRole('textbox', { name: 'Ask Omni' }).fill('What facility context is selected?')
  await page.getByRole('button', { name: 'Send' }).click()
  const body = (await request).postDataJSON()
  expect(body.context.selected_account_id).toBe(accountId)
  expect(body.context.selected_facility_id).toBe('public-hq-lockheed-martin')
})

test('federal route, Relationship Intelligence, governed Action, Omni and Back share one version', async ({ page }) => {
  let action
  await page.route(/\/api\/actions(?:\?.*)?$/, async route => {
    if (route.request().method() === 'POST') {
      const input = route.request().postDataJSON()
      action = { ...input, id: 'action-federal-navigation', status: 'OPEN', approval_status: 'NOT_REQUIRED', version: 1, created_by: 'seller-1', created_at: '2026-09-16T12:00:00Z', updated_at: '2026-09-16T12:00:00Z' }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(action) })
    }
    const response = await route.fetch(); const body = await response.json()
    if (action) body.items = [action, ...body.items.filter(item => item.id !== action.id)]
    await route.fulfill({ response, json: body })
  })
  await page.route('**/api/actions/action-federal-navigation/history', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ events: [] }) }))
  await page.goto('/#/intelligence?view=federal')
  await page.getByRole('button', { name: 'Aerospace precision component sources sought' }).click()
  const opportunityUrl = page.url()
  expect(opportunityUrl).toContain('opportunity=SAM-1')
  await page.getByRole('button', { name: 'Explore relationship route' }).click()
  await expect(page.getByText('Federal opportunity starting context')).toBeVisible()
  expect(page.url()).toContain('view=relationships'); expect(page.url()).toContain('opportunity=SAM-1')
  await page.goBack(); await expect(page.getByRole('heading', { name: 'Federal Procurement' })).toBeVisible()
  await page.getByRole('button', { name: 'Create or review Action proposal' }).click()
  await expect(page.getByText('Federal opportunity context')).toBeVisible()
  const actionUrl = page.url(); expect(actionUrl).toContain('action='); expect(actionUrl).toContain('opportunity=SAM-1')
  await page.reload(); await expect(page.getByText('Federal opportunity context')).toBeVisible()
  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByText('Aware of: selected federal opportunity')).toBeVisible()
  await page.goBack(); await expect(page.getByRole('heading', { name: 'Federal Procurement' })).toBeVisible()
})

test('Actions state, copied links, malformed links and permission denial recover safely on desktop and mobile', async ({ page, context }) => {
  await page.goto('/#/actions?view=suggestions&f.priority=HIGH&sort=DUE')
  await expect(page.getByRole('heading', { name: 'Actions', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Suggested' })).toHaveAttribute('aria-current', 'page')
  expect(page.url()).toContain('f.priority=HIGH'); expect(page.url()).toContain('sort=DUE')

  const deepLink = new URL('/#/map?account_id=lockheed-martin&facility=public-hq-lockheed-martin&scope=facility', page.url()).href
  const copied = await context.newPage(); await copied.goto(deepLink)
  await expect(copied.getByRole('heading', { name: 'Lockheed Martin' }).first()).toBeVisible()
  await copied.close()

  await page.goto('/#/map?scope=facility&assessment=partial')
  await expect(page.getByText(/malformed or no longer supported/i)).toBeVisible()
  expect(page.url()).not.toContain('assessment=partial')

  const restricted = await context.newPage()
  await restricted.route('**/api/accounts/restricted-account', route => route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Top secret account name' }) }))
  await restricted.goto('/#/accounts/restricted-account')
  await expect(restricted.getByText(/unavailable or you do not have access/i)).toBeVisible()
  await expect(restricted.getByText('Top secret account name')).toHaveCount(0)
  await restricted.close()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(deepLink)
  await expect(page.getByRole('heading', { name: 'Lockheed Martin' }).first()).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})
