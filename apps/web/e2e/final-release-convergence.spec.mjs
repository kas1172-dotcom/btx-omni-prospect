import { expect, test } from '@playwright/test'

const primary = ['Today', 'Profiles', 'Intelligence', 'Map', 'Actions']

const documentFitsViewport = page => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)

test('release surfaces remain free of React/runtime errors and restore drawer focus', async ({ page }) => {
  const errors = []
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('pageerror', error => errors.push(error.message))

  await page.goto('/')
  const navigation = page.getByRole('navigation', { name: 'Primary navigation' })
  for (const label of [...primary, 'Communications']) {
    await navigation.getByRole('button', { name: label, exact: true }).click()
    await expect(page.locator('.page-title h1')).toBeVisible()
    expect(await documentFitsViewport(page)).toBe(true)
  }
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible()

  await navigation.getByRole('button', { name: 'Map', exact: true }).click()
  const filters = page.getByRole('button', { name: 'Layers & filters' })
  await filters.click()
  await expect(page.getByRole('dialog', { name: 'Layers & filters' })).toBeVisible()
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: 'Layers & filters' })).toHaveCount(0)
  await expect(filters).toBeFocused()

  await navigation.getByRole('button', { name: 'Today', exact: true }).click()
  await page.getByLabel('Open Omni assistant').click()
  await page.getByRole('button', { name: 'What should I review today?' }).click()
  await expect(page.locator('.message.assistant')).toBeVisible()
  await page.getByRole('button', { name: 'Open in Omni' }).click()
  await expect(page.getByRole('dialog', { name: 'Omni' })).toBeVisible()
  await page.getByLabel('Close Full Omni').click()

  expect(errors, errors.join('\n')).toEqual([])
})

for (const viewport of [{ width: 390, height: 844 }, { width: 320, height: 700 }, { width: 430, height: 932 }]) {
  test(`mobile release matrix fits every major surface at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.goto('/')
    const navigation = page.getByRole('navigation', { name: 'Mobile primary navigation' })
    for (const label of primary) {
      await navigation.getByRole('button', { name: label, exact: true }).click()
      await expect(page.locator('.surface')).toBeVisible()
      expect(await documentFitsViewport(page)).toBe(true)
    }

    for (const label of ['Communications', 'Settings']) {
      const menu = navigation.getByRole('button', { name: 'More', exact: true })
      if (await menu.getAttribute('aria-expanded') !== 'true') await menu.click()
      await page.getByRole('button', { name: label, exact: true }).click()
      await expect(page.locator('.surface')).toBeVisible()
      expect(await documentFitsViewport(page)).toBe(true)
    }

    await page.getByLabel('Open Omni assistant').click()
    await expect(page.getByRole('dialog', { name: 'Ask Omni' })).toBeVisible()
    expect(await documentFitsViewport(page)).toBe(true)
    await page.getByRole('button', { name: 'Open in Omni' }).click()
    await expect(page.getByRole('dialog', { name: 'Omni' })).toBeVisible()
    expect(await documentFitsViewport(page)).toBe(true)
  })
}
