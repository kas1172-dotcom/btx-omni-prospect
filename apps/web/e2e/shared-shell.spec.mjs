import { expect, test } from '@playwright/test'

const primaryDestinations = ['Today', 'Customers & Prospects', 'Intelligence', 'Map', 'Actions']

async function expectSurface(page, name) {
  await expect(page.locator('.page-title h1')).toHaveText(name === 'Map' ? 'Tactical Map' : name)
}

test('desktop target shell preserves primary seller navigation and Omni access', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/')

  const shell = page.locator('.app-shell:not(.app-shell-loading)')
  const navigation = page.getByRole('navigation', { name: 'Primary navigation' })
  await expect(shell).toBeVisible()
  await expect(navigation).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Mobile primary navigation' })).toBeHidden()

  for (const destination of primaryDestinations) {
    const control = navigation.getByRole('button', { name: destination, exact: true })
    await control.click()
    await expectSurface(page, destination)
    await expect(control).toHaveAttribute('aria-current', 'page')
  }

  await expect(page.getByLabel('Open Omni assistant')).toBeVisible()
  await page.getByLabel('Open Omni assistant').click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeVisible()

  const shellCopy = `${await page.locator('.app-sidebar').innerText()} ${await page.locator('.topbar').innerText()}`
  expect(shellCopy).toContain('Customers & Prospects')
  expect(shellCopy).not.toMatch(/\b(Account|Accounts|Client|Clients|Company|Companies)\b/)
})

test('390 × 844 target shell uses five safe touch destinations without overflow or Omni collision', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')

  const shell = page.locator('.app-shell:not(.app-shell-loading)')
  const navigation = page.getByRole('navigation', { name: 'Mobile primary navigation' })
  // The shell is usable only after the governed bootstrap leaves its explicit
  // loading state; this remains deterministic under default parallel workers.
  await expect(page.locator('.app-shell-loading')).toBeHidden({ timeout: 15_000 })
  await expect(shell).toBeVisible()
  await expect(navigation).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Primary navigation', exact: true })).toBeHidden()

  const controls = navigation.getByRole('button')
  await expect(controls).toHaveCount(5)
  expect(await controls.allTextContents()).toEqual(primaryDestinations)

  for (const destination of primaryDestinations) {
    const control = navigation.getByRole('button', { name: destination, exact: true })
    const box = await control.boundingBox()
    expect(box?.height).toBeGreaterThanOrEqual(44)
    await control.click()
    await expectSurface(page, destination)
    await expect(control).toHaveAttribute('aria-current', 'page')
  }

  await navigation.getByRole('button', { name: 'Today', exact: true }).click()
  const metrics = await page.evaluate(() => {
    const workspace = document.querySelector('.app-workspace')
    const nav = document.querySelector('.mobile-primary-nav')
    const omni = document.querySelector('.omni-launch')
    const navBox = nav?.getBoundingClientRect()
    const omniBox = omni?.getBoundingClientRect()
    return {
      documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      shellOverflow: document.querySelector('.app-shell')?.scrollWidth - document.documentElement.clientWidth,
      workspacePaddingBottom: workspace ? Number.parseFloat(getComputedStyle(workspace).paddingBottom) : 0,
      navHeight: navBox?.height ?? 0,
      overlapsOmni: Boolean(navBox && omniBox && omniBox.bottom > navBox.top),
    }
  })
  expect(metrics.documentOverflow).toBeLessThanOrEqual(1)
  expect(metrics.shellOverflow).toBeLessThanOrEqual(1)
  expect(metrics.workspacePaddingBottom).toBeGreaterThanOrEqual(metrics.navHeight)
  expect(metrics.overlapsOmni).toBe(false)
  await expect(page.getByLabel('Open Omni assistant')).toBeVisible()
})

test('320px shell smoke check remains structurally contained', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  await page.goto('/')
  await expect(page.getByRole('navigation', { name: 'Mobile primary navigation' }).getByRole('button')).toHaveCount(5)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})
