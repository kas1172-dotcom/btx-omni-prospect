import { defineConfig } from '@playwright/test'

const apiPort = process.env.BTX_E2E_API_PORT ?? '8000'
const webPort = process.env.BTX_E2E_WEB_PORT ?? '5173'

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  webServer: [
    {
      command: `uv run uvicorn btx_omni.app:app --host 127.0.0.1 --port ${apiPort}`,
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
        BTX_MONITOR_OPERATOR_TOKEN: '',
        BTX_FEDERAL_PROCUREMENT_FIXTURE_MODE: 'true',
        BTX_ACTION_SALESPERSON_TOKEN: 'development-salesperson',
        BTX_ACTION_MANAGER_TOKEN: 'development-manager',
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${webPort}`,
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
  },
})
