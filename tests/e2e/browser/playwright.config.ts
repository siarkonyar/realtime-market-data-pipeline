import { defineConfig, devices } from '@playwright/test'

// The app the browser opens. By default the Docker stack: nginx on port 3000
// with the real api behind it, so start it first (docker compose up).
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000'
const IS_CI = Boolean(process.env.CI)

export default defineConfig({
  testDir: '.',
  // A test.only left in by mistake would make CI run just that one test.
  forbidOnly: IS_CI,
  // On CI a second try tells a flaky test apart from a broken one.
  retries: IS_CI ? 2 : 0,
  use: {
    baseURL: BASE_URL,
    // Records each step of a failed retry; replay it with `npx playwright show-trace`.
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
