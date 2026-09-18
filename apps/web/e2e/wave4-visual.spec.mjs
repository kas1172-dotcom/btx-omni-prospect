import { expect, test } from '@playwright/test'

for (const [width, height] of [[320, 800], [390, 844], [768, 1024], [1440, 900]]) {
  test(`Wave 4 map and itinerary remain usable at ${width}×${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/#/map')
    if (width <= 900) await page.getByRole('button', { name: 'List', exact: true }).click()
    await page.getByRole('region', { name: 'Map results', exact: true }).getByRole('button').filter({ hasText: /^KLA Corporation/ }).first().click()
    const detail = page.getByRole('complementary', { name: 'Selected map location', exact: true })
    await expect(detail).toBeVisible()
    for (const tab of ['Overview', 'Commercial', 'Contacts', 'Sources']) await expect(detail.getByRole('tab', { name: tab, exact: true })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Tactical Map V2 workspace', exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
    await page.screenshot({ path: testInfo.outputPath(`map-selected-${width}x${height}.png`) })

    await detail.getByRole('button', { name: 'Add to itinerary', exact: true }).click()
    const itinerary = page.getByRole('dialog', { name: 'Itinerary', exact: true })
    await expect(itinerary).toContainText('Route timing unavailable')
    await expect(itinerary.getByRole('button', { name: /Move .* earlier/ }).first()).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
    await page.screenshot({ path: testInfo.outputPath(`itinerary-${width}x${height}.png`) })
  })
}
