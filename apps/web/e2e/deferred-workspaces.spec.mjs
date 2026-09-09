import { test, expect } from '@playwright/test'

async function signInProductionPreview(page, testInfo) {
  if (process.env.BTX_PRODUCTION_CHUNK_CHECK === '1') {
    // Production JS against the isolated development API, not hosted acceptance.
    // Exchange its existing fixture access code through the actual session route.
    expect(testInfo.project.use.baseURL).toBe('http://127.0.0.1:5186')
    const session = await page.request.post('/api/session/sign-in', { data: { access_code: 'development-salesperson' } })
    expect(session.ok()).toBe(true)
  }
}

test('off-route workspace code is deferred and a failed Map download is recoverable', async ({ page }, testInfo) => {
  await signInProductionPreview(page, testInfo)
  let mapRequests = 0
  const requests = []
  await page.route(/\/(?:src\/features\/map\/Map\.tsx|assets\/Map-[\w-]+\.js)(?:\?.*)?$/, async route => {
    mapRequests += 1
    requests.push(route.request().url())
    if (mapRequests === 1) await route.abort('failed')
    else await route.continue()
  })
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Primary navigation', exact: true })
  await expect(nav).toBeVisible()
  expect(mapRequests).toBe(0)
  await nav.getByRole('button', { name: 'Map', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Map could not be downloaded' })).toBeVisible()
  await expect(nav).toBeVisible()
  await expect(page).toHaveURL(/#\/map$/)
  await page.getByRole('button', { name: 'Retry Map download', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Tactical Map', exact: true })).toBeVisible()
  await testInfo.attach('map-module-requests', { body: JSON.stringify(requests), contentType: 'application/json' })
  expect(mapRequests).toBe(2)
  await nav.getByRole('button', { name: 'Today', exact: true }).click()
  await nav.getByRole('button', { name: 'Map', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Tactical Map', exact: true })).toBeVisible()
  expect(mapRequests).toBe(2)
})

test('workspace recovery does not depend on an import error containing its URL', async ({ page }, testInfo) => {
  await signInProductionPreview(page, testInfo)
  let attempts = 0
  await page.route(/\/(?:src\/features\/map\/Map\.tsx|assets\/Map-[\w-]+\.js)(?:\?.*)?$/, async route => {
    attempts += 1
    if (attempts === 1) await route.fulfill({ contentType: 'text/javascript', body: 'throw new TypeError("Importing a module script failed.")' })
    else await route.continue()
  })
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Primary navigation', exact: true }).getByRole('button', { name: 'Map', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Map could not be downloaded' })).toBeVisible()
  await page.getByRole('button', { name: 'Retry Map download', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Tactical Map', exact: true })).toBeVisible()
  expect(attempts).toBe(2)
})
