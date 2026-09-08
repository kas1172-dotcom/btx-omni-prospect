import { expect, test } from '@playwright/test'

const priorityCustomers = [
  'Honeywell', 'Boeing', 'KLA Corporation', 'SpaceX', 'Intuitive Surgical',
  'Lockheed Martin', 'Woodward', 'Northrop Grumman', 'HUXWRX', 'Eaton', 'Emerson',
]

async function openPortfolio(page) {
  const navigationName = (await page.viewportSize())?.width <= 768 ? 'Mobile primary navigation' : 'Primary navigation'
  await page.goto('/')
  await page.getByRole('navigation', { name: navigationName }).getByRole('button', { name: 'Customers & Prospects' }).click()
}

test('all priority Customers are discoverable and rich/reference scenarios remain truthful', async ({ page }) => {
  const honeywell = await (await page.request.get('/api/accounts/honeywell')).json()
  const huxwrx = await (await page.request.get('/api/accounts/huxwrx')).json()
  await openPortfolio(page)
  const search = page.getByRole('searchbox', { name: 'Search Customers and Prospects' })
  for (const name of priorityCustomers) {
    await search.fill(name)
    await expect(page.locator('.portfolio-table-row').filter({ hasText: name })).toHaveCount(1)
  }

  await search.fill('Honeywell')
  await page.locator('.portfolio-table-row').filter({ hasText: 'Honeywell' }).click()
  await expect(page.getByRole('heading', { name: 'Honeywell', level: 1 })).toBeVisible()
  await expect(page.getByText('SANITIZED REFERENCE SOURCE', { exact: true })).toBeVisible()
  await expect(page.getByText('SIMULATED BTX CONTEXT', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Commercial context available')).toBeVisible()
  await expect(page.getByText('Cross Bu Coordination')).toBeVisible()
  if (honeywell.commercial_briefing) {
    expect(honeywell.public_contacts.length).toBeGreaterThan(0)
    for (const contact of honeywell.public_contacts) {
      expect(contact.contact_type).toBe('PUBLIC_CONTACT_CANDIDATE')
      expect(contact.provenance.research_only).toBe(true)
      const evidence = page.getByRole('article').filter({ has: page.getByText(contact.name, { exact: true }) })
      await expect(evidence.getByRole('link', { name: 'Inspect source →', exact: true })).toHaveAttribute('href', contact.source_url)
    }
  } else await expect(page.getByText('No verified public contact is available.', { exact: false })).toBeVisible()

  await page.getByRole('searchbox', { name: 'Switch Customer' }).fill('HUXWRX')
  await page.getByRole('option', { name: /HUXWRX/ }).click()
  await expect(page.getByRole('heading', { name: 'HUXWRX', level: 1 })).toBeVisible()
  if (huxwrx.commercial_briefing) {
    expect(huxwrx.orders.length).toBeGreaterThan(0)
    expect(huxwrx.commercial_briefing.summary).toBe('A seasonal replenishment increase needs a release plan')
    await expect(page.getByText(huxwrx.commercial_briefing.summary, { exact: true })).toBeVisible()
    await expect(page.getByText(huxwrx.commercial_briefing.next_action, { exact: true }).first()).toBeVisible()
    await expect(page.getByText('No Commercial record is linked to this canonical Customer.')).toHaveCount(0)
  } else {
    await expect(page.getByText('No Commercial record is linked to this canonical Customer.')).toBeVisible()
    await expect(page.getByText('No governed alert is currently open')).toBeVisible()
    await expect(page.getByText('No eligible validated connection is currently available for this Customer.')).toBeVisible()
  }
})

for (const width of [390, 320]) test(`priority Customer disclosures remain usable at ${width}px`, async ({ page }) => {
  const eaton = await (await page.request.get('/api/accounts/eaton')).json()
  await page.setViewportSize({ width, height: 844 })
  await openPortfolio(page)
  await page.getByRole('searchbox', { name: 'Search Customers and Prospects' }).fill('Eaton')
  await page.locator('.portfolio-mobile-list .ui-mobile-row').filter({ hasText: 'Eaton' }).click()
  await expect(page.getByRole('heading', { name: 'Eaton', level: 1 })).toBeVisible()
  const attention = page.getByRole('button', { name: /What needs attention/ })
  await expect(attention).toHaveAttribute('aria-expanded', 'true')
  if (eaton.commercial_briefing) {
    expect(eaton.commercial_briefing.summary).toBe('The newest housing shipment is awaiting acceptance')
    await expect(page.getByText(eaton.commercial_briefing.summary, { exact: true })).toBeVisible()
    await expect(page.getByText(eaton.commercial_briefing.next_action, { exact: true }).first()).toBeVisible()
  } else await expect(page.getByText('BOOKINGS DECLINE', { exact: true })).toBeVisible()
  const commercial = page.getByRole('button', { name: /Commercial context/ })
  await commercial.click()
  await expect(commercial).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByText('Simulated BTX commercial context')).toBeVisible()
  await expect(page.getByLabel('Open Omni assistant')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})
