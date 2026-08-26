import { defineConfig } from '@playwright/test'

// E2E smoke tests run against the real stack: Vite dev server proxying
// to the FastAPI backend with PostgreSQL. Locally, already-running dev
// servers are reused; in CI the webServer commands start them.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command:
        'python -m uvicorn app.main:app --port 8000 --app-dir ../backend',
      url: 'http://localhost:8000/api/v1/health',
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 30_000,
    },
  ],
})
