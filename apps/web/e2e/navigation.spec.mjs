import { test, expect } from '@playwright/test'

test('portfolio search and sort survive a customer and another surface', async ({ page }) => {
  await page.goto('/#/accounts')
  const search = page.getByRole('searchbox', { name: 'Search Customers and Prospects', exact: true })
  await search.fill('Lockheed')
  await page.getByRole('button', { name: /Attractiveness/ }).click()
  await page.getByRole('table', { name: 'Customers and Prospects' }).getByRole('link', { name: 'Lockheed Martin', exact: true }).click()
  await page.getByRole('button', { name: '← Customers & Prospects', exact: true }).click()
  await expect(search).toHaveValue('Lockheed')
  await expect(page.getByRole('columnheader', { name: /Attractiveness/ })).toHaveAttribute('aria-sort', 'descending')
  const nav = page.getByRole('navigation', { name: 'Primary navigation', exact: true })
  await nav.getByRole('button', { name: 'Today', exact: true }).click()
  await nav.getByRole('button', { name: 'Customers & Prospects', exact: true }).click()
  await expect(search).toHaveValue('Lockheed')
})

test('canonical account deep link survives refresh and browser back/forward', async ({ page }) => {
  await page.goto('/#/accounts/kla')
  const heading = page.getByRole('heading', { name: 'KLA Corporation', exact: true }).first()
  await expect(heading).toBeVisible()
  await page.reload()
  await expect(heading).toBeVisible()
  const nav = page.getByRole('navigation', { name: 'Primary navigation', exact: true })
  await nav.getByRole('button', { name: 'Customers & Prospects', exact: true }).click()
  await expect(page).toHaveURL(/#\/accounts(?:\?|$)/)
  await expect(page.getByRole('heading', { name: 'Customers & Prospects', exact: true })).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(/#\/accounts\/kla(?:\?|$)/)
  await expect(heading).toBeVisible()
  await page.goForward()
  await expect(page.getByRole('heading', { name: 'Customers & Prospects', exact: true })).toBeVisible()
})

test('malformed account links cannot become account API paths', async ({ page }) => {
  const reads = []
  page.on('request', request => { if (request.url().includes('/api/accounts/')) reads.push(request.url()) })
  await page.goto('/#/accounts/%2E%2E%2Fsettings')
  await expect(page.getByRole('heading', { name: 'Customers & Prospects', exact: true })).toBeVisible()
  expect(reads).toEqual([])
})
