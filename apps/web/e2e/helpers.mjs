import { expect } from '@playwright/test'

export async function openCustomerSection(page, name) {
  const tabs = page.getByRole('tablist', { name: 'Profile sections' })
  const label = String(name)
  if (/Growth & research planning/i.test(label)) {
    const planning = page.locator('.profile-planning-popover')
    await expect(planning.locator('summary')).toBeVisible()
    if (await planning.getAttribute('open') === null) await planning.locator('summary').click()
    return planning
  }
  const tab = /relationship|contacts/i.test(label) ? 'Relationships' : /intelligence/i.test(label) ? 'Intelligence' : /Related BTX|Commercial 360|Commercial context|Commercial decisions/i.test(label) ? 'More' : /program|capabilit|opportunit|Growth|planning/i.test(label) ? 'Overview' : /Actions/i.test(label) ? 'Actions' : /Commercial|Decision panel/i.test(label) ? 'Commercial' : undefined
  if (tab) {
    await expect(tabs).toBeVisible()
    await tabs.getByRole('tab', { name: tab, exact: true }).click()
  }
  if (/Commercial context/i.test(label)) await openOrganizationEvidence(page)
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
  // Desktop graph is now secondary, not automatically visible on profile entry.
  if (page.viewportSize().width > 760) {
    const graphToggle = workspace.getByRole('button', { name: 'Explore network', exact: true })
    if (await graphToggle.count()) await graphToggle.click()
  }
  return workspace
}

export async function openOrganizationEvidence(page) {
  const tabs = page.getByRole('tablist', { name: 'Profile sections' })
  await expect(tabs).toBeVisible()
  await tabs.getByRole('tab', { name: 'More', exact: true }).click()
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

export async function openRecordedDecision(page) {
  const close = page.getByRole('button', { name: 'Close supporting evidence' })
  if (await close.isVisible()) await close.click()
  await page.getByRole('tab', { name: 'More', exact: true }).click()
  const trigger = page.getByRole('button', { name: 'Recorded decision context', exact: true })
  if (await trigger.getAttribute('aria-expanded') !== 'true') await trigger.click()
  return page.getByRole('region', { name: 'Organization decision summary' })
}
