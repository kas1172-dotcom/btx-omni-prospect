import { expect, test } from '@playwright/test'
import { openCustomerSection } from './helpers.mjs'

async function openOpportunity(page, { mobile = false } = {}) {
  await page.goto('/#/intelligence/federal')
  if (mobile) await expect(page.getByText(/Understand the requirement, compare supported routes/)).toBeVisible()
  else await expect(page.getByRole('heading', { name: 'Federal Procurement' })).toBeVisible()
  await page.getByRole('button', { name: 'Aerospace precision component sources sought' }).click()
  await expect(page.getByRole('heading', { name: 'Work with this route' })).toBeVisible()
}

test('canonical opportunity opens its organization and evidence-backed relationship context', async ({ page }) => {
  await openOpportunity(page)
  await expect(page.getByRole('button', { name: 'Open organization profile' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Explore relationship route' })).toBeVisible()
  await page.getByRole('button', { name: 'Explore relationship route' }).click()
  await expect(page.getByRole('heading', { name: 'Eaton', exact: true })).toBeVisible()
  await expect(page.getByText('Federal opportunity starting context')).toBeVisible()
  await expect(page.getByText(/Missing agency, program, qualification or introduction hops remain validation gaps/)).toBeVisible()
})

test('opportunity opens Omni with the canonical route and governed next action', async ({ page }) => {
  await openOpportunity(page)
  await page.getByRole('button', { name: 'Ask Omni about this opportunity' }).click()
  await expect(page.getByText('Aware of: selected federal opportunity')).toBeVisible()
  const request = page.waitForRequest(item => item.url().endsWith('/api/omni') && item.method() === 'POST')
  const response = page.waitForResponse(item => item.url().endsWith('/api/omni') && item.request().method() === 'POST')
  await page.getByRole('textbox', { name: 'Ask Omni' }).fill('What should I validate next?')
  await page.getByRole('button', { name: 'Send' }).click()
  const body = (await request).postDataJSON()
  expect(body.context.selected_federal_opportunity.opportunity_id).toBe('SAM-1')
  expect(body.context.selected_federal_opportunity.route_type).toBe('CUSTOMER_EXPANSION')
  await response
  await expect(page.locator('.message.assistant').last()).toContainText(/validate|review|research/i)
})

test('governed Action proposal is durable and restores the same opportunity context', async ({ page }) => {
  await openOpportunity(page)
  const create = page.waitForResponse(response => response.url().endsWith('/api/actions') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Create or review Action proposal' }).click()
  expect((await create).ok()).toBeTruthy()
  await expect(page.getByRole('heading', { name: 'Actions', exact: true })).toBeVisible()
  await expect(page.getByText('Federal opportunity context')).toBeVisible()
  await expect(page.getByText(/this internal proposal performed no external write/i)).toBeVisible()
})

test('strategic route exposes only the governed partnership entry point and joint-pursuit hypothesis', async ({ page }) => {
  let assessment
  const accountResponse = await page.request.get('/api/accounts/eaton')
  const accountBody = await accountResponse.json()
  const planningResponse = await page.request.get('/api/planning')
  const planningBody = await planningResponse.json()
  await page.route(/\/api\/federal-procurement(?:\?.*)?$/, async route => {
    const response = await route.fetch()
    const body = await response.json()
    assessment = body.active.opportunities[0].assessment
    const partner = { ...assessment.routes.find(item => item.route_type === 'CUSTOMER_EXPANSION'), route_type: 'STRATEGIC_PARTNER', label: 'Joint pursuit to validate' }
    assessment = { ...assessment, routes: [partner, ...assessment.routes.filter(item => item.route_type !== 'CUSTOMER_EXPANSION')], account_routes: [partner], recommended_route: partner }
    body.active.opportunities[0].assessment = assessment
    await route.fulfill({ response, json: body })
  })
  await page.route('**/api/accounts/eaton', async route => {
    const body = structuredClone(accountBody)
    body.federal_opportunities = [{ ...assessment, account_routes: [assessment.recommended_route] }]
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.route('**/api/federal-procurement/assessments/*', async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(assessment) })
  })
  await page.route('**/api/planning', async route => {
    const body = structuredClone(planningBody)
    const designation = { account_id: 'eaton', designated: true, reason: 'Governed complementary capability review.', version: 1, updated_by: 'manager', updated_at: '2026-09-16T12:00:00Z' }
    body.strategic_partnerships = [designation]; body.partnership_records = [designation]
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await openOpportunity(page)
  await expect(page.getByRole('button', { name: 'Open Strategic Partnership profile' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open organization profile' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Open Strategic Partnership profile' }).click()
  await expect(page.getByRole('heading', { name: 'Eaton', exact: true })).toBeVisible()
  await openCustomerSection(page, /Growth & research planning/)
  await expect(page.getByRole('heading', { name: 'Potential joint pursuits' })).toBeVisible()
  const pursuits = page.getByRole('region', { name: 'Potential joint federal pursuits' })
  await pursuits.getByRole('button', { name: /View supporting evidence/ }).click()
  await expect(pursuits.getByText(/qualified pursuit hypothesis/i)).toBeVisible()
})

test('mobile workflow keeps route actions reachable without page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openOpportunity(page, { mobile: true })
  await expect(page.getByRole('button', { name: 'Ask Omni about this opportunity' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(overflow).toBeFalsy()
})
