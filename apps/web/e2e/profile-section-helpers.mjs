import { expect } from '@playwright/test'

export async function openProfileSection(page, title, tab) {
  await page.getByRole('tab', { name: tab, exact: true }).click()
  const disclosure = page.getByRole('button', { name: title })
  await expect(disclosure).toBeVisible()
  if (await disclosure.getAttribute('aria-expanded') === 'false') await disclosure.click()
  await expect(disclosure).toHaveAttribute('aria-expanded', 'true')
}
