import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const phase = process.argv[2] ?? 'baseline'
if (!/^[a-z0-9-]+$/.test(phase)) throw new Error('Invalid phase')
const directory = resolve('../../docs/redesign', phase)
await mkdir(directory, { recursive: true })
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('http://127.0.0.1:5328/#/accounts')
  await page.locator('.portfolio-data-table').waitFor()
  await page.screenshot({ path: resolve(directory, 'list.png'), fullPage: true })
  await page.goto('http://127.0.0.1:5328/#/accounts/boeing')
  await page.getByRole('heading', { name: 'Boeing', exact: true, level: 1 }).waitFor()
  for (const name of ['Overview', 'Commercial', 'Intelligence', 'Actions', 'Relationships']) {
    const tab = page.getByRole('tab', { name, exact: true })
    if (await tab.count()) {
      await tab.click()
      await page.waitForLoadState('networkidle')
      if (['step5', 'step6', 'final'].includes(phase) && name === 'Commercial') {
        await page.getByRole('heading', { name: 'Commercial decision panel', exact: true }).waitFor({ timeout: 30000 })
      }
      if (['step6', 'final'].includes(phase) && name === 'Relationships') {
        await page.locator('.ranked-relationships[aria-busy="false"]').waitFor({ timeout: 30000 })
        await page.waitForLoadState('networkidle')
        // Let the initial selection/context render settle before checking again.
        await page.waitForTimeout(1000)
        await page.locator('.ranked-relationships[aria-busy="false"]').waitFor({ timeout: 30000 })
      }
      await page.screenshot({ path: resolve(directory, `boeing-${name.toLowerCase()}.png`), fullPage: true })
    } else console.log(`${phase}: ${name} tab absent; no screenshot fabricated`)
  }
  const accounts = await (await page.request.get('http://127.0.0.1:8128/api/accounts')).json()
  const prospect = accounts.accounts.find(item => ['TARGET', 'PROSPECT', 'PUBLIC_MARKET'].includes(item.relationship))
  if (!prospect) throw new Error('No canonical prospect available')
  await page.goto(`http://127.0.0.1:5328/#/accounts/${encodeURIComponent(prospect.id)}`)
  await page.getByRole('heading', { name: prospect.name, exact: true, level: 1 }).waitFor()
  await page.screenshot({ path: resolve(directory, 'prospect.png'), fullPage: true })
  console.log(JSON.stringify({ phase, prospect: prospect.id, pageErrors: errors }))
  if (errors.length) process.exitCode = 1
} finally { await browser.close() }
