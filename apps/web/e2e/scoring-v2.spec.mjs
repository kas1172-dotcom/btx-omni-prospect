import { test, expect } from '@playwright/test'
import { openCustomerSection } from './helpers.mjs'

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test(`v2 account scoring, disclosure and unknown pursuit inputs at ${viewport.width}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('/#/accounts/huxwrx')
    await expect(page.getByRole('heading', { name: 'HUXWRX', exact: true, level: 1 })).toBeVisible()
    const response = await page.request.get('/api/accounts/huxwrx/commercial/decisions')
    expect(response.ok()).toBeTruthy()
    const decisions = await response.json()
    expect(decisions.customer_health.score).toBe('72.50')
    expect(decisions.internal_commercial_risk.score).toBe('23.75')
    expect(Number(decisions.customer_health.data_coverage.ratio)).toBe(1)
    expect(decisions.customer_health.configuration_version).toBe('BTX_SCORING_RUBRIC_V2')
    expect(decisions.opportunities.every(item => item.pwin.score === null && item.delivery_feasibility.score === null)).toBeTruthy()
    await openCustomerSection(page, /Commercial decisions & follow-ups/)
    const health = page.getByRole('article', { name: 'Customer health score summary' })
    await expect(health).toContainText('72.5/100')
    await expect(health).not.toContainText('ACC-HUXWRX')
    const disclosure = health.getByRole('button', { name: 'Why this?' })
    await expect(disclosure).toHaveAttribute('aria-expanded', 'false')
    await disclosure.click()
    const explanation = page.getByRole('dialog', { name: 'Why this?', exact: true })
    await expect(explanation).toContainText('Calculated result: 72.50/100')
    await expect(explanation).toContainText('Factors driving this result')
    await page.getByRole('button', { name: 'Close explanation' }).click()
    await expect(page.getByRole('article', { name: 'Internal commercial risk score summary' })).toContainText('23.75/100')
    await expect(page.getByRole('article', { name: 'Pwin score summary' }).first()).toContainText('Not applicable yet')
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1)
    await health.scrollIntoViewIfNeeded()
    await page.screenshot({ path: process.env.BTX_SCORING_SCREENSHOT_DIR ? `${process.env.BTX_SCORING_SCREENSHOT_DIR}/scores-${viewport.width}.png` : testInfo.outputPath('scores.png') })
    expect(errors).toEqual([])
  })
}
