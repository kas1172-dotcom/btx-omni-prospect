import { expect, test } from '@playwright/test'
import { readOmniAnswer } from './omni-stream-helpers.mjs'

for (const width of [390, 1440]) {
  test(`Omni records a private answer and retries receipt inspection at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await page.goto('/#/accounts/boeing')
    await page.getByLabel('Open Omni assistant').click()
    const pending = page.waitForResponse(response => response.url().endsWith('/api/omni/chat/stream') && response.request().method() === 'POST')
    await page.locator('#omni-message').fill('Summarize Boeing commercial context.')
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    const response = await pending
    expect(response.status()).toBe(200)
    const answer = await readOmniAnswer(response, page)
    expect(answer.run_id).toMatch(/^[0-9a-f-]{36}$/)
    let attempts = 0
    let allowRead = false
    await page.route(`**/api/omni/runs/${answer.run_id}`, async route => {
      attempts++
      if (!allowRead) return route.fulfill({ status: 503, body: 'Temporary read failure' })
      return route.continue()
    })
    const message = page.locator('.message.assistant').last()
    await message.getByRole('button', { name: 'Details', exact: true }).click()
    await message.getByRole('button', { name: 'Answer receipt', exact: true }).click()
    await expect(message.getByRole('alert')).toContainText('The displayed answer is unchanged')
    await expect(message).toContainText(answer.content.slice(0, 60))
    const initialAttempts = attempts
    expect(initialAttempts).toBeGreaterThan(0)
    allowRead = true
    const receiptResponse = page.waitForResponse(r => r.url().endsWith('/api/omni/runs/' + answer.run_id) && r.status() === 200)
    await message.getByRole('button', { name: 'Retry run receipt', exact: true }).click()
    const receipt = await (await receiptResponse).json()
    expect(receipt.result.answer).toBe(answer.content)
    expect(receipt.result.execution).toMatchObject({ external_writes: 0, work_writes: 0, memory_writes: 0 })
    expect(receipt.status).toBe('ANSWER_RECORDED')
    await expect(message).toContainText(answer.run_id)
    expect(attempts).toBe(initialAttempts + 1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await testInfo.attach('private-run-receipt', { body: JSON.stringify(receipt, null, 2), contentType: 'application/json' })
    await message.screenshot({ path: testInfo.outputPath(`omni-run-${width}.png`) })
  })
}
