import { expect, test } from '@playwright/test'

test('Federal Procurement shows ranked SAMPLE opportunities, filters, detail, and evidence', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Intelligence', exact: true }).click()
  await page.getByRole('button', { name: 'Federal Procurement' }).click()
  await expect(page.getByRole('heading', { name: 'Federal Procurement' })).toBeVisible()
  await expect(page.getByText(/SAM.gov: SAMPLE/)).toBeVisible()
  await expect(page.getByText(/Aerospace precision component/)).toBeVisible()
  await page.getByLabel('Filter federal opportunities by notice type').selectOption('Sources Sought')
  await expect(page.getByRole('button', { name: 'View relevance & evidence' })).toHaveCount(1)
  await page.getByRole('button', { name: 'View relevance & evidence' }).click()
  await expect(page.getByText('Why it matters to BTX')).toBeVisible()
  await expect(page.getByRole('link', { name: /official SAM.gov evidence/ })).toBeVisible()
})

test('Federal Procurement awarded dollars has FY and scope disclosures', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Intelligence', exact: true }).click()
  await page.getByRole('button', { name: 'Federal Procurement' }).click()
  await page.getByRole('tab', { name: 'Awarded Dollars' }).click()
  await expect(page.getByText(/USAspending: SAMPLE/)).toBeVisible()
  await page.getByLabel('Select fiscal year').selectOption('2025')
  await expect(page.getByText('Top prime recipients')).toBeVisible()
  await expect(page.getByText('Supply-chain lag')).toBeVisible()
})
