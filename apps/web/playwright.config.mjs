import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  webServer: [
    {
      command: 'uv run uvicorn btx_omni.app:app --host 127.0.0.1 --port 8000',
      cwd: '../../backend',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'VITE_MAP_TEST_MODE=true npm run dev -- --host 127.0.0.1 --port 5173',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    headless: true,
  },
})
