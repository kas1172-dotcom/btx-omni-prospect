import { defineConfig } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const database = join(mkdtempSync(join(tmpdir(), 'btx-opportunities-ui-')), 'browser.sqlite').replaceAll('\\', '/')
const backendCommand = 'uv run --frozen python -c "from sqlalchemy import create_engine; from btx_omni.core.config import get_settings; from btx_omni.app import app; from btx_omni.persistence.models import metadata; metadata.create_all(create_engine(get_settings().database_url)); import uvicorn; uvicorn.run(app, host=\'127.0.0.1\', port=18439)"'

// Isolated UI verification: no durable store, imports, migrations or production writes.
export default defineConfig({
  testDir: './e2e',
  testMatch: 'opportunities-rebuild.spec.mjs',
  timeout: 45_000,
  workers: 1,
  reporter: [['list']],
  outputDir: 'test-results/opportunities',
  webServer: [
    {
      command: backendCommand,
      cwd: '../../backend', url: 'http://127.0.0.1:18439/api/health', timeout: 120_000,
      env: { ...process.env, BTX_DATABASE_URL: `sqlite:///${database}`, BTX_ENVIRONMENT: 'development', BTX_DATA_MODE: 'SAMPLE', BTX_COMMERCIAL_DURABLE_STATE_ENABLED: 'false', BTX_MONITOR_DURABLE_STATE_ENABLED: 'false', BTX_MARKET_REFRESH_ENABLED: 'false', BTX_GEMINI_API_KEY: '', GEMINI_API_KEY: '', GOOGLE_API_KEY: '', BTX_ACTION_SALESPERSON_TOKEN: 'development-salesperson', BTX_ACTION_MANAGER_TOKEN: 'development-manager', BTX_FEDERAL_PROCUREMENT_FIXTURE_MODE: 'true' },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 15439 --strictPort',
      url: 'http://127.0.0.1:15439', timeout: 120_000,
      env: { ...process.env, VITE_MAP_TEST_MODE: 'true', VITE_API_PROXY_TARGET: 'http://127.0.0.1:18439' },
    },
  ],
  use: { baseURL: 'http://127.0.0.1:15439', headless: true, browserName: 'chromium', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
})
