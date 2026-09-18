import { defineConfig } from '@playwright/test'

const apiPort = process.env.BTX_E2E_API_PORT ?? '8000'
const webPort = process.env.BTX_E2E_WEB_PORT ?? '5173'

export default defineConfig({
  testDir: './e2e',
  // Separate required gates: production-session configuration and real durable
  // public collection cannot be substituted by this deterministic fixture suite.
  testIgnore: ['hosted-demo-access.spec.mjs', 'monitor-public-evidence.spec.mjs'],
  timeout: 45_000,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
  webServer: [
    {
      command: `uv run --frozen uvicorn btx_omni.app:app --host 127.0.0.1 --port ${apiPort}`,
      cwd: '../../backend',
      url: `http://127.0.0.1:${apiPort}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        BTX_AI_PROVIDER: 'gemini',
        BTX_GEMINI_API_KEY: '',
        GEMINI_API_KEY: '',
        GOOGLE_API_KEY: '',
        BTX_ENVIRONMENT: 'development',
        BTX_DATA_MODE: 'SAMPLE',
        BTX_GEMINI_MODEL: '',
        BTX_COMMERCIAL_DURABLE_STATE_ENABLED: 'true',
        BTX_MONITOR_DURABLE_STATE_ENABLED: 'true',
        BTX_MARKET_REFRESH_ENABLED: 'false',
        BTX_MONITOR_OPERATOR_TOKEN: '',
        BTX_FEDERAL_PROCUREMENT_FIXTURE_MODE: 'true',
        BTX_ACTION_SALESPERSON_TOKEN: 'development-salesperson',
        BTX_ACTION_MANAGER_TOKEN: 'development-manager',
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`,
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        VITE_MAP_TEST_MODE: 'true',
        VITE_API_PROXY_TARGET: `http://127.0.0.1:${apiPort}`,
      },
    },
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? `http://127.0.0.1:${webPort}`,
    headless: true,
    browserName: process.env.BTX_E2E_BROWSER === 'webkit' ? 'webkit' : 'chromium',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
})
