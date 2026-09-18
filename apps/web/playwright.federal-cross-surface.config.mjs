import { defineConfig } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL
if (!baseURL) throw new Error('E2E_BASE_URL is required for the task-owned federal workflow server.')

export default defineConfig({
  testDir: './e2e',
  testMatch: 'federal-cross-surface.spec.mjs',
  timeout: 45_000,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: 'test-results/federal-cross-surface.json' }]],
  use: {
    baseURL,
    headless: true,
    browserName: 'chromium',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
})
