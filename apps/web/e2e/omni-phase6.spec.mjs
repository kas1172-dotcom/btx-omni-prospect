import { expect, test } from '@playwright/test'

test.describe.configure({ mode: 'serial' })

async function waitForApp(page) {
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible({ timeout: 15_000 })
}

async function openOmni(page) {
  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeVisible()
}

async function closeOmni(page) {
  await page.getByLabel('Close Omni').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeHidden()
}

async function ask(page, question) {
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/omni') && response.request().method() === 'POST')
  await page.locator('#omni-message').fill(question)
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const response = await responsePromise
  expect(response.status()).toBe(200)
  const body = await response.json()
  const request = response.request().postDataJSON()
  await expect(page.locator('.message.assistant').last()).toContainText(body.content.slice(0, 48))
  return { request, body }
}

async function navigate(page, name) {
  await page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('button', { name }).click()
  await expect(page.locator('.page-title h1')).toHaveText(name)
}

test('Phase 6 Omni browser acceptance preserves typed context, continuity, and isolation', async ({ page }) => {
  await page.goto('/')
  await waitForApp(page)
  await expect(page.locator('.page-title h1')).toHaveText('Today')

  // Screen summary comes from the actual current UI context.
  await openOmni(page)
  const today = await ask(page, 'What am I looking at?')
  expect(today.request.context.surface).toBe('TODAY')
  expect(today.body.context_used.surface).toBe('TODAY')
  await closeOmni(page)

  // Select event A through the UI, then carry its typed referent into a follow-up.
  await navigate(page, 'Intelligence')
  await expect(page.getByRole('button', { name: 'Use in Omni' }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Use in Omni' }).first().click()
  await openOmni(page)
  const eventA = await ask(page, 'Why does this matter?')
  const eventAId = eventA.request.context.selected_event_id
  expect(eventAId).toBeTruthy()
  expect(eventA.body.context_used.event_id).toBe(eventAId)
  expect(eventA.body.conversation_referent.event_id).toBe(eventAId)
  await closeOmni(page)
  await page.getByRole('button', { name: 'Clear Omni event' }).click()
  await openOmni(page)
  const eventFollowUp = await ask(page, 'Which account is it tied to?')
  expect(eventFollowUp.request.context.selected_event_id).toBeUndefined()
  expect(eventFollowUp.request.context.conversation_referent.event_id).toBe(eventAId)
  expect(eventFollowUp.body.context_used.context_source).toBe('conversation')
  await closeOmni(page)

  // Select event B: a current same-type UI selection must supersede event A.
  await page.getByRole('button', { name: 'Use in Omni' }).nth(1).click()
  await openOmni(page)
  const eventB = await ask(page, 'Why is this important?')
  expect(eventB.request.context.selected_event_id).toBeTruthy()
  expect(eventB.request.context.selected_event_id).not.toBe(eventAId)
  expect(eventB.body.context_used.event_id).toBe(eventB.request.context.selected_event_id)
  expect(eventB.body.context_used.context_source).toBeUndefined()
  await closeOmni(page)

  // Leaving Intelligence clears its passive event selection before an Accounts summary.
  await navigate(page, 'Customers & Prospects')
  await openOmni(page)
  const cleared = await ask(page, 'Summarize this screen.')
  expect(cleared.request.context.selected_event_id).toBeUndefined()
  expect(cleared.body.context_used.surface).toBe('ACCOUNTS')
  await closeOmni(page)

  // A current market filter is serialized, then absent after clearing it.
  await page.getByRole('button', { name: 'Defense', exact: true }).click()
  await openOmni(page)
  const filtered = await ask(page, 'What matters most on this page?')
  expect(filtered.request.context.active_filters.market).toBe('Defense')
  expect(filtered.body.context_used.filters.market).toBe('Defense')
  await closeOmni(page)
  await page.getByRole('button', { name: 'All industries', exact: true }).click()
  await openOmni(page)
  const filterCleared = await ask(page, 'What matters most on this page?')
  expect(filterCleared.request.context.active_filters?.market).toBeUndefined()
  expect(filterCleared.body.context_used.filters?.market).toBeUndefined()

  // A global request does not inherit the event or a conversational entity as scope.
  const global = await ask(page, 'Which accounts have the highest attractiveness scores?')
  expect(global.request.context.selected_event_id).toBeUndefined()
  expect(global.request.context.conversation_referent).toBeUndefined()
  expect(global.body.context_used.event_id).toBeUndefined()
  expect(global.body.context_used.account_id).toBeUndefined()
})

test('Quick Omni opens the Full Omni workspace without losing the conversation', async ({ page }) => {
  await page.goto('/')
  await waitForApp(page)
  await openOmni(page)
  await ask(page, 'What should I review today?')
  await page.getByRole('button', { name: 'Open in Omni' }).click()
  const full = page.getByRole('dialog', { name: 'Omni' })
  await expect(full).toBeVisible()
  await expect(full.locator('.message.user')).toContainText('What should I review today?')
  await expect(full.getByRole('complementary', { name: 'Evidence' })).toBeVisible()
  await expect(full.getByRole('complementary', { name: 'Organization context' })).toBeVisible()
  await expect(full.getByText(/create|edit|assign|approve/i)).not.toBeVisible()
  await page.getByLabel('Back to Quick Omni').click()
  await expect(page.locator('.quick-omni .message.user')).toContainText('What should I review today?')
})

test('an immediately launched selected assessment reaches Omni before submission', async ({ page }) => {
  const assessment = {
    id: 'assessment-context-event', context_id: 'assessment-context-event:lockheed-martin', assessment_id: 'a'.repeat(64), assessment_version: 2,
    canonical_account_ids: ['lockheed-martin'], canonical_program_id: null, headline: 'Supported public development', seller_summary: 'A supported public development requires account review.',
    what_happened: 'A source-backed public development was recorded.', why_it_may_matter: 'The event is relevant to the selected Customer context.', what_to_watch: 'Watch for material scope changes.',
    recommended_action: 'Review the cited notice before changing any customer commitment.', action_rationale: 'The evidence supports review, not an automatic commitment.', material_uncertainties: [],
    markets: ['Defense'], event_timing: 'RECENT', freshness: 'CURRENT', data_mode: 'LIVE_PUBLIC', analysis_status: 'READY', commercial_relevance_state: 'ESTABLISHED_ACCOUNT_REVIEW', summary_mode: 'DETERMINISTIC',
    publication_timestamp: '2026-09-01T00:00:00Z', relevant_event_timestamp: '2026-09-01T00:00:00Z', source_system: 'Official source', source_url: 'https://example.com/source', resolution_state: 'RESOLVED', seller_promotion_state: 'ELIGIBLE',
    evidence_ids: ['PUBLIC-EVIDENCE'], references: [], priority_reasons: [], missing_fields: [],
    signal_confidence: { score: 84.71, factors: [{ key: 'source_quality', points: 90, reason: 'Official source.', evidence_ids: ['PUBLIC-EVIDENCE'] }], data_coverage: { present: 1, applicable: 1 }, decision_id: 'signal-confidence-test', configuration_version: 'SIGNAL_CONFIDENCE_1', input_configuration_version: 'ASSESSMENT_INPUT_1' },
  }
  await page.route('**/api/today', async route => {
    const response = await route.fetch()
    const payload = await response.json()
    const item = { id: 'public-assessment-priority', kind: 'PUBLIC_SIGNAL', account_id: 'lockheed-martin', event_id: assessment.id, reason: assessment.why_it_may_matter, recommended_action: assessment.recommended_action, observed_at: assessment.publication_timestamp, evidence_ids: assessment.evidence_ids, business_unit_ids: [], signal_brief: assessment }
    payload.command_center.priority_briefing = [item, ...payload.command_center.priority_briefing]
    await route.fulfill({ response, json: payload })
  })
  await page.route('**/api/omni', async route => {
    const request = route.request().postDataJSON()
    if (!request.question.includes('selected assessment')) return route.continue()
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ content: 'Signal Confidence: 84.71/100. Next step: Review the cited notice before changing any customer commitment.', account_id: 'lockheed-martin', account_name: 'Lockheed Martin', citations: ['PUBLIC-EVIDENCE'], citation_links: [{ label: 'Official source', url: 'https://example.com/source' }], provenance: ['STORED_INTELLIGENCE'], missingness: [], recommended_action: assessment.recommended_action, context_used: { assessment_id: assessment.assessment_id, assessment_version: assessment.assessment_version }, provider_status: 'AVAILABLE', language_provider: 'deterministic' }) })
  })
  await page.goto('/')
  await waitForApp(page)
  await page.getByRole('button', { name: 'Public intelligence', exact: true }).click()
  const priority = page.locator('.today-attention-item').filter({ hasText: assessment.headline })
  await priority.getByRole('button', { name: 'Evidence and next action' }).click()
  await priority.getByRole('button', { name: /View supporting evidence/ }).click()
  const scoreSummary = priority.getByRole('article', { name: 'Signal Confidence score summary' })
  await expect(scoreSummary).toContainText(String(assessment.signal_confidence.score))
  const expectedScore = String(assessment.signal_confidence.score)
  const expectedAction = await priority.locator('.today-priority-meaning > p').filter({ hasText: 'Next:' }).innerText()
  await priority.getByRole('button', { name: 'Use in Omni', exact: true }).click()
  await openOmni(page)
  const answer = await ask(page, 'Explain this selected assessment, including its Signal Confidence and recommended action.')
  expect(answer.request.context.selected_assessment).toMatchObject({
    assessment_id: expect.any(String),
    assessment_version: expect.any(Number),
    event_id: answer.request.context.selected_event_id,
    account_id: expect.any(String),
  })
  expect(answer.body.context_used.assessment_id).toBe(answer.request.context.selected_assessment.assessment_id)
  expect(answer.body.context_used.assessment_version).toBe(answer.request.context.selected_assessment.assessment_version)
  expect(answer.body.content).toContain(`Signal Confidence: ${expectedScore}/100`)
  expect(answer.body.recommended_action).toBe(expectedAction.replace(/^Next:\s*/, ''))
})

test('mobile Quick and Full Omni use touch-safe sheet and mode navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await waitForApp(page)
  await openOmni(page)
  const quick = page.locator('.quick-omni')
  await expect(quick).toBeVisible()
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await page.getByRole('button', { name: 'Open in Omni' }).click()
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click()
  await expect(page.getByRole('complementary', { name: 'Evidence' })).toBeVisible()
  await page.getByRole('tab', { name: 'Organization context', exact: true }).click()
  await expect(page.getByRole('complementary', { name: 'Organization context' })).toBeVisible()
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  await page.setViewportSize({ width: 320, height: 844 })
  await expect(page.getByRole('tab', { name: 'Conversation' })).toBeVisible()
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('Omni replaces prompt starters with a readable current exchange', async ({ page }) => {
  await page.goto('/')
  await waitForApp(page)
  await openOmni(page)
  await expect(page.getByLabel('Prompt starters')).toBeVisible()
  await expect(page.locator('#omni-message')).toBeFocused()
  const result = await ask(page, 'Which accounts have open quotes?')
  await expect(page.getByLabel('Prompt starters')).toBeHidden()
  await expect(page.locator('.conversation .message.user').last()).toContainText('Which accounts have open quotes?')
  await expect(page.locator('.conversation .message.assistant').last()).toContainText(result.body.content.slice(0, 48))
  await expect(page.locator('.omni-compose')).toBeVisible()
})

test('Monitor sends its truthful typed surface without scoping global Omni queries', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
  await page.goto('/')
  await waitForApp(page)
  await navigate(page, 'Source Health')
  await openOmni(page)
  const monitor = await ask(page, 'What am I looking at?')
  expect(monitor.request.context.surface).toBe('MONITOR')
  expect(monitor.body.context_used.surface).toBe('MONITOR')
  expect(monitor.body.content).toContain('Monitor exposes status and provenance')
  const global = await ask(page, 'Which accounts have the highest scores?')
  expect(global.request.context.surface).toBe('MONITOR')
  expect(global.body.context_used.surface).toBeUndefined()
  expect(global.body.context_used.account_id).toBeUndefined()
})
