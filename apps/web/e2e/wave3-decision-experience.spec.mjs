import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const evidenceDir = process.env.BTX_WAVE3_EVIDENCE_DIR
const shot = (testInfo, name) => {
  const directory = evidenceDir ?? testInfo.outputDir
  mkdirSync(directory, { recursive: true })
  return join(directory, name)
}

for (const viewport of [{ name: 'desktop', width: 1440, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
  test(`Wave 3 Organization 360 and relationship decision hierarchy · ${viewport.name}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/#/accounts/lockheed-martin')
    await expect(page.getByRole('heading', { name: 'Lockheed Martin', level: 1 })).toBeVisible()
    const overview = page.locator('.profile-overview')
    await expect(overview).toContainText('Data Coverage')
    await expect(overview.getByRole('heading', { name: 'TTM commercial activity' })).toBeVisible()
    await expect(overview.getByRole('heading', { name: 'Relationship coverage by function' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
    await page.screenshot({ path: shot(testInfo, `organization-360-${viewport.name}.png`), fullPage: true })
    await page.getByRole('tab', { name: 'Relationships', exact: true }).click()
    const ranked = page.getByRole('region', { name: 'Ranked canonical relationships' })
    await expect(ranked).toHaveAttribute('aria-busy', 'false')
    await expect(ranked.getByRole('heading', { name: /^Selected route/ })).toBeVisible()
    if (viewport.name === 'mobile') await expect(ranked.getByRole('button', { name: 'Explore network' })).toBeVisible()
    else {
      await expect(ranked.locator('.ranked-network')).toBeHidden()
      await ranked.getByRole('button', { name: 'Explore network', exact: true }).click()
      await expect(ranked.getByRole('group', { name: 'Canonical relationship network' })).toBeVisible()
    }
    await expect(ranked).not.toContainText(/needs check|PUBLISHED_ROLE_AT|CAPABILITY_MATCH/)
    await expect(ranked).toContainText(/Recorded relationship|Needs validation|Possible route to investigate/)
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
    await page.screenshot({ path: shot(testInfo, `relationship-intelligence-${viewport.name}.png`), fullPage: true })
  })
}

test('Settings-origin focus question stays scope-safe and provider detail is secondary', async ({ page }) => {
  await page.goto('/#/settings')
  await page.getByLabel('Open Omni assistant').click()
  await page.locator('#omni-message').fill('What should I focus on today?')
  await page.locator('#omni-message').press('Enter')
  const response = page.locator('.message.assistant').last()
  await expect(response).toContainText('Open Today')
  await expect(response).toContainText("The AI service isn't available right now")
  await expect(response).not.toContainText(/DOM|screenshots|backend universe|unsupported surface/i)
  await response.getByRole('button', { name: 'Details', exact: true }).click()
  const delivery = response.getByRole('button', { name: 'Answer delivery details' })
  await expect(delivery).toHaveAttribute('aria-expanded', 'false')
})
