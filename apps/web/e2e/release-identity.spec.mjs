import { expect, test } from '@playwright/test'

for (const width of [390, 1440]) {
  test(`release diagnostics cross actual API and expose unverified builds at ${width}`, async ({ page }, testInfo) => {
    await page.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    const frontend = await (await page.request.get('/build.json')).json()
    const backend = await (await page.request.get('/api/build')).json()
    expect(frontend.repository).toBe('kas1172-dotcom/btx-omni-prospect')
    expect(backend.repository).toBe(frontend.repository)
    await page.goto('/#/settings')
    const disclosure = page.getByRole('button', { name: 'Frontend and backend build identity', exact: true })
    await disclosure.focus()
    await page.keyboard.press('Enter')
    const panel = disclosure.locator('..')
    await expect(panel).toContainText(frontend.commit_sha ?? 'Not recorded')
    await expect(panel).toContainText(backend.required_schema_revision)
    if (frontend.worktree !== 'clean' || backend.worktree !== 'clean') await expect(panel).toContainText('Release identity is not verified.')
    await expect(page.locator('html')).toHaveJSProperty('scrollWidth', width)
    await panel.screenshot({ path: testInfo.outputPath(`build-identity-${width}.png`) })
    expect(errors).toEqual([])
  })
}

test('a mismatched backend declaration is visibly rejected, not rendered as release success', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('btx-principal-token', 'development-manager'))
  // Deliberate negative payload only; the two preceding tests use actual API data.
  await page.route('**/api/settings', async route => {
    const response = await route.fetch()
    const body = await response.json()
    body.release_diagnostics.build = { ...body.release_diagnostics.build, commit_sha: 'f'.repeat(40) }
    await route.fulfill({ response, json: body })
  })
  await page.goto('/#/settings')
  await page.getByRole('button', { name: 'Frontend and backend build identity', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Version mismatch: frontend and backend do not identify the same release.')
})
