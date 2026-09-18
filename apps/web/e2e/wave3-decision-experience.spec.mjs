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
    const decision = page.getByRole('region', { name: 'Organization decision summary' })
    await expect(decision).toContainText('What changed')
    await expect(decision).toContainText('Why it matters')
    await expect(decision).toContainText('Material uncertainty')
    await expect(decision).toContainText('Governed next action')
    await expect(decision).toContainText('Data Coverage')
    const relationship = page.locator('.account-workspace-relationship')
    await expect(relationship.getByText('Best governed route')).toBeVisible()
    const fullWorkspace = relationship.getByRole('button', { name: 'Open full Relationship Intelligence workspace' })
    await expect(fullWorkspace).toHaveAttribute('aria-expanded', 'false')
    await expect(page.getByRole('region', { name: 'Ranked canonical relationships' })).toHaveCount(0)
    const decisionBox = await decision.boundingBox()
    const relationshipBox = await relationship.boundingBox()
    expect(decisionBox.y).toBeLessThan(relationshipBox.y)
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
    await page.screenshot({ path: shot(testInfo, `organization-360-${viewport.name}.png`), fullPage: true })

    await fullWorkspace.click()
    const ranked = page.getByRole('region', { name: 'Ranked canonical relationships' })
    await expect(ranked).toHaveAttribute('aria-busy', 'false')
    await expect(ranked.getByRole('heading', { name: /^Selected route/ })).toBeVisible()
    if (viewport.name === 'mobile') await expect(ranked.getByRole('button', { name: 'Explore network' })).toBeVisible()
    else await expect(ranked.getByRole('group', { name: 'Canonical relationship network' })).toBeVisible()
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
  await expect(response).toContainText('choose an organization or assessment')
  await expect(response).not.toContainText(/DOM|screenshots|backend universe|unsupported surface/i)
  const delivery = response.getByRole('button', { name: 'Answer delivery details' })
  await expect(delivery).toHaveAttribute('aria-expanded', 'false')
})
