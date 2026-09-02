import { expect, test } from '@playwright/test'

test('explicit SAMPLE hosted-demo bypass enters as Salesperson without exposing a code', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.app-shell:not(.app-shell-loading)')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Hosted POC access')).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Today', exact: true })).toBeVisible()

  // The local production-mode server intentionally sets a Secure cookie. The
  // Vite test origin is HTTP, so preserve the server-issued opaque session in
  // the browser context solely to exercise protected UI after direct entry.
  const sessionResponse = await page.request.get('/api/session')
  const sessionCookie = sessionResponse.headers()['set-cookie']?.match(/btx_poc_session=([^;]+)/)?.[1]
  expect(sessionCookie).toBeTruthy()
  await page.context().addCookies([{ name: 'btx_poc_session', value: sessionCookie, url: `${new URL(page.url()).origin}/api`, httpOnly: true, secure: false, sameSite: 'Lax' }])
  await page.reload()

  await page.getByRole('button', { name: 'Settings', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible()
  const identity = page.locator('.settings-identity')
  await expect(identity.getByText('POC Salesperson', { exact: true })).toBeVisible()
  await expect(identity.getByText('Salesperson', { exact: true })).toBeVisible()
  await expect(page.getByText('Restricted', { exact: true })).toHaveCount(2)
  await page.getByText('Safe release diagnostics', { exact: true }).click()
  await expect(page.getByText('Sample demo auto session', { exact: true })).toBeVisible()

  const authorization = await page.evaluate(async () => {
    const session = await fetch('/api/session').then(response => response.json())
    const created = await fetch('/api/actions', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify({
        account_id: 'boeing',
        title: `Hosted demo authorization ${Date.now()}`,
        priority: 'MEDIUM',
        approval_required: true,
      }),
    }).then(response => response.json())
    const approval = await fetch(`/api/actions/${created.id}/approval`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'X-CSRF-Token': session.csrf_token },
      body: JSON.stringify({ decision: 'APPROVED' }),
    })
    return { role: session.principal.role, approvalStatus: approval.status }
  })
  expect(authorization.role).toBe('SALESPERSON')
  expect(authorization.approvalStatus).toBe(403)
})
