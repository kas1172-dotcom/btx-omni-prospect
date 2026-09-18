import { expect } from '@playwright/test'

export async function openCustomerSection(page, name) {
  const trigger = page.getByRole('button', { name }).first()
  await expect(trigger).toBeVisible()
  if (await trigger.getAttribute('aria-expanded') !== 'true') await trigger.click()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  return trigger
}

export async function openRelationshipWorkspace(page) {
  await openCustomerSection(page, /People and relationship paths/)
  const trigger = page.getByRole('button', { name: 'Open full Relationship Intelligence workspace' })
  await expect(trigger).toBeVisible()
  if (await trigger.getAttribute('aria-expanded') !== 'true') await trigger.click()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  const workspace = page.getByRole('region', { name: 'Ranked canonical relationships', exact: true })
  await expect(workspace).toHaveAttribute('aria-busy', 'false')
  return workspace
}

export async function openOrganizationEvidence(page) {
  const trigger = page.locator('.supporting-evidence-trigger').last()
  await expect(trigger).toBeVisible()
  await trigger.click()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  return page.viewportSize().width <= 760
    ? page.getByRole('dialog', { name: 'Supporting evidence' })
    : page.locator('.supporting-evidence-body').last()
}

export async function selectSuggestion(page, id) {
  const row = page.locator(`[data-suggestion-id="${id}"]`)
  await expect(row).toBeVisible()
  await row.click()
  const detail = page.locator('.suggestion-detail')
  await expect(detail).toBeVisible()
  return detail
}
