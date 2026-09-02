import { defineConfig } from '@playwright/test'

const apiPort = process.env.BTX_HOSTED_DEMO_API_PORT ?? '8101'
const webPort = process.env.BTX_HOSTED_DEMO_WEB_PORT ?? '5174'

export default defineConfig({
  testDir: './e2e',
  testMatch: 'hosted-demo-access.spec.mjs',
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
        BTX_ENVIRONMENT: 'production',
        BTX_DATA_MODE: 'SAMPLE',
        BTX_HOSTED_DEMO_ACCESS_BYPASS: 'true',
        BTX_AI_PROVIDER: 'gemini',
        BTX_GEMINI_API_KEY: '',
        GEMINI_API_KEY: '',
        GOOGLE_API_KEY: '',
        BTX_MONITOR_OPERATOR_TOKEN: '',
        BTX_FEDERAL_PROCUREMENT_FIXTURE_MODE: 'true',
        BTX_ACTION_SALESPERSON_TOKEN: 'hosted-demo-test-salesperson',
        BTX_ACTION_MANAGER_TOKEN: 'hosted-demo-test-manager',
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
    baseURL: `http://127.0.0.1:${webPort}`,
    headless: true,
  },
})
