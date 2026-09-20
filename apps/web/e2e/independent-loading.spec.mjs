import { test, expect } from '@playwright/test'

test('a held optional map read does not block the account journey', async ({ page }) => {
  let release
  const held = new Promise(resolve => { release = resolve })
  await page.route('**/api/map', async route => { await held; await route.continue().catch(() => {}) })
  try {
    await page.goto('/')
    await page.getByRole('navigation', { name: 'Primary navigation', exact: true }).getByRole('button', { name: 'Profiles', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Profiles', exact: true })).toBeVisible()
    await expect(page.getByRole('row', { name: /^KLA/ }).first()).toBeVisible()
    await page.getByRole('navigation', { name: 'Primary navigation', exact: true }).getByRole('button', { name: 'Map', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('Loading Map')
    release()
    await expect(page.getByRole('heading', { name: 'Tactical Map', exact: true })).toBeVisible()
  } finally { release() }
})

test('navigation cancels an unfinished account read without late context takeover', async ({ page }) => {
  let release
  const held = new Promise(resolve => { release = resolve })
  await page.route('**/api/accounts/kla', async route => { await held; await route.continue().catch(() => {}) })
  try {
    await page.goto('/')
    const nav = page.getByRole('navigation', { name: 'Primary navigation', exact: true })
    await nav.getByRole('button', { name: 'Profiles', exact: true }).click()
    await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: 'KLA Corporation', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('Opening')
    await nav.getByRole('button', { name: 'Map', exact: true }).click()
    release()
    await expect(page.getByRole('heading', { name: 'Tactical Map', exact: true })).toBeVisible()
    await expect(page.getByRole('status').filter({ hasText: 'Opening' })).toHaveCount(0)
    await expect(nav.getByRole('button', { name: 'Map', exact: true })).toHaveAttribute('aria-current', 'page')
  } finally { release() }
})

test('map filters and a canonical selected site survive Account360 navigation', async ({ page }) => {
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Primary navigation', exact: true })
  await nav.getByRole('button', { name: 'Map', exact: true }).click()
  await page.getByRole('button', { name: 'Layers & filters', exact: true }).click()
  await page.getByRole('group', { name: 'Industry and market', exact: true }).getByRole('button', { name: 'Semiconductor', exact: true }).click()
  await page.getByRole('button', { name: 'Apply to map', exact: true }).click()
  const list = page.getByRole('region', { name: 'Map results', exact: true })
  const site = list.getByRole('button').filter({ hasText: /^KLA/ }).first()
  await site.click()
  const selected = page.getByRole('complementary', { name: 'Selected map location', exact: true })
  await expect(selected).toBeVisible()
  await expect(selected).toContainText('KLA Corporation')
  const selectedSite = await selected.getByRole('heading', { level: 2 }).innerText()
  await selected.getByRole('button', { name: 'Open Organization 360', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'KLA Corporation', exact: true }).first()).toBeVisible()
  await nav.getByRole('button', { name: 'Map', exact: true }).click()
  await expect(selected).toContainText('KLA Corporation')
  await expect(selected.getByRole('heading', { level: 2 })).toHaveText(selectedSite, { useInnerText: true })
  await expect(page.getByRole('button', { name: 'Remove Semiconductor filter', exact: true })).toBeVisible()
})
