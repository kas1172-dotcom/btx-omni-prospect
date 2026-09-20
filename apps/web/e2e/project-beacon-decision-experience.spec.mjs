import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'

const evidenceDir = process.env.BTX_EVIDENCE_DIR

async function capture(page, name) {
  if (!evidenceDir) return
  await mkdir(evidenceDir, { recursive: true })
  await page.screenshot({ path: join(evidenceDir, `${name}.png`), fullPage: false })
}

async function expectNoPageOverflow(page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
}

test('Project Beacon leads with a specific decision, governed importance, and a concise score', async ({ page }) => {
  await page.goto('/#/accounts/applied-materials?scope=account')
  await expect(page.getByRole('heading', { name: 'Applied Materials receives $100 million advanced-packaging award' })).toBeVisible()
  await expect(page.getByText('High importance', { exact: true })).toBeVisible()
  await expect(page.getByText(/silicon-core substrate work could create precision hardware, tooling, or equipment-support demand/i)).toBeVisible()
  await expect(page.getByText(/program-level BTX fit and a commercial route have not yet been established/i)).toBeVisible()
  await expect(page.getByText('84.3/100', { exact: true })).toBeVisible()
  await expect(page.getByText(/public semiconductor-equipment context supports fit discovery/i)).toHaveCount(0)
  await capture(page, 'organization-360-applied-materials-desktop')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByText('High importance', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
  await capture(page, 'organization-360-applied-materials-mobile')
})

test('Intelligence presents the research library without duplicating Today priorities', async ({ page }) => {
  await page.goto('/#/intelligence?sort=PRIORITY')
  await expect(page.getByRole('button', { name: 'Public Intelligence', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: "Today's Priority Signals" })).toHaveCount(0)
  await expect(page.getByText('Action priorities', { exact: true })).toHaveCount(0)
  await expect(page.getByText(/No fresh collection in this session · saved intelligence remains available/)).toBeVisible()
  await expect(page.getByRole('button', { name: /Tracked Profiles/ })).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('heading', { name: 'Intelligence Feed' })).toBeVisible()
  const applied = page.locator('.intelligence-card').filter({ hasText: 'Applied Materials receives $100 million advanced-packaging award' })
  await expect(applied).toContainText('The funded silicon-core substrate work could create precision hardware, tooling, or equipment-support demand')
  await expect(applied).toContainText('Research direction · not yet assessed')
  await expect(applied).not.toContainText('linked to a canonical Customer or Prospect')
  await capture(page, 'intelligence-decision-feed-desktop')
})

test('Omni explains the selected Applied Materials evidence in human language', async ({ page }) => {
  await page.goto('/#/intelligence?sort=PRIORITY')
  await page.getByLabel('Filter Intelligence by Customer').selectOption('applied-materials')
  const applied = page.locator('.intelligence-card').filter({ hasText: 'Applied Materials receives $100 million advanced-packaging award' })
  await expect(applied).toHaveCount(1)
  await applied.getByRole('button', { name: 'Use in Omni' }).click()
  await page.getByLabel('Open Omni assistant').click()
  const drawer = page.getByRole('dialog', { name: 'Ask Omni' })
  await expect(drawer).toContainText('Aware of: Applied Materials')
  await drawer.getByRole('textbox').fill('What changed, why might it matter to BTX, and what should I validate next?')
  await drawer.getByRole('button', { name: /Send/i }).click()
  await expect(drawer).toContainText(/Applied Materials briefing/i)
  await expect(drawer).toContainText(/What changed:/i)
  await expect(drawer).toContainText(/Why it may matter to BTX:/i)
  await expect(drawer).toContainText(/What to validate next:/i)
  await expect(drawer).not.toContainText(/Canonical account follow-up|source-backed Intelligence|CHIPS_APPLIED/)
  await capture(page, 'omni-applied-materials-grounded-answer')
})

test('Project Beacon mobile command surfaces remain concise, reachable, and overflow-free', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/today')
  await expect(page.getByRole('heading', { name: 'Today', level: 1 })).toBeVisible()
  await expect(page.locator('.today-priority-summary')).toBeVisible()
  await expectNoPageOverflow(page)
  await capture(page, 'today-mobile')

  const mobileNav = page.getByRole('navigation', { name: 'Mobile primary navigation' })
  await mobileNav.getByRole('button', { name: 'Intelligence' }).click()
  await expect(page.locator('.topbar-context').getByText('Intelligence', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: "Today's Priority Signals" })).toHaveCount(0)
  await expect(page.getByText(/saved intelligence remains available/)).toBeVisible()
  await expect(page.locator('.intelligence-card').first()).toBeVisible()
  await expectNoPageOverflow(page)
  await capture(page, 'intelligence-mobile')

  await mobileNav.getByRole('button', { name: 'Map' }).click()
  await expect(page.getByRole('heading', { name: 'Tactical Map' })).toBeVisible()
  await page.getByRole('button', { name: 'List', exact: true }).click()
  const result = page.getByRole('region', { name: 'Map results', exact: true }).getByRole('button').filter({ hasText: /customer site · inspect details/i }).first()
  await result.click()
  await expect(page.getByRole('complementary', { name: 'Selected map location' })).toBeVisible()
  await expectNoPageOverflow(page)
  await capture(page, 'map-selected-site-mobile')

  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeVisible()
  await expectNoPageOverflow(page)
  await capture(page, 'omni-mobile')
})
