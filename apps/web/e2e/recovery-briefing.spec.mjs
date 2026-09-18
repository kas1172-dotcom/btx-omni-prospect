import { expect, test } from '@playwright/test'

const priorityId = 'alert-overdue_order-ORD2-BOEING-2026-08-1'

test('Boeing recovery briefing renders the canonical reconciliation and opens its governed proposal', async ({ page }) => {
  await page.goto(`/#/today/brief/${encodeURIComponent(priorityId)}`)
  const canonical = await page.evaluate(async () => (await fetch('/api/accounts/boeing')).json())
  const fulfillment = canonical.commercial_briefing.fulfillment

  await expect(page.getByRole('heading', { name: canonical.commercial_briefing.summary, level: 1 })).toBeVisible()
  await expect(page.locator('.recovery-metrics strong')).toHaveText([
    String(fulfillment.ordered_quantity),
    String(fulfillment.shipped_quantity),
    String(fulfillment.remaining_quantity),
    '$143,080',
  ])
  await expect(page.getByText('Proposal not completed', { exact: true })).toBeVisible()
  await expect(page.getByText(/Unassigned · role/)).toBeVisible()
  await expect(page.getByRole('button', { name: /Underlying commercial records/ })).toHaveAttribute('aria-expanded', 'false')
  await page.getByRole('button', { name: /Underlying commercial records/ }).click()
  const evidence = page.getByRole('complementary', { name: 'Recovery actions and evidence' }).locator('.recovery-evidence-list')
  for (const evidenceId of canonical.commercial_briefing.evidence_ids) await expect(evidence.getByText(evidenceId, { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Create action proposal' }).click()
  await expect(page).toHaveURL(/#\/actions\?view=suggestions/)
  await expect(page.getByText('Showing the recommendation linked to your Today priority.')).toBeVisible()
  await expect(page.getByText('Confirm fulfillment status and customer recovery plan.', { exact: true }).last()).toBeVisible()
})

test('recovery briefing preserves exact quantities and does not overflow on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/today/brief/${encodeURIComponent(priorityId)}`)
  await expect(page.locator('.recovery-metrics strong')).toHaveText(['292', '146', '146', '$143,080'])
  await expect(page.getByRole('button', { name: 'Create action proposal' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
})
