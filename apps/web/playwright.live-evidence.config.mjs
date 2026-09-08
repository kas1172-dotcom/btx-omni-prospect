import { defineConfig } from '@playwright/test'

// No automatic server, SAMPLE fixture setup or model substitution. This gate
// needs previously collected real durable evidence on the verified target.
const baseURL = process.env.E2E_BASE_URL
if (!baseURL || !['https://btx-omni-prospect.vercel.app', 'http://127.0.0.1:5184'].includes(baseURL)) throw new Error('Choose the verified Omni Prospect hosted URL or the task-owned real-provider local preview.')

export default defineConfig({
  testDir: './e2e',
  testMatch: 'monitor-public-evidence.spec.mjs',
  timeout: 45_000,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: 'test-results/live-evidence-results.json' }]],
  use: { baseURL, headless: true, browserName: 'chromium', storageState: process.env.BTX_E2E_STORAGE_STATE, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
})
