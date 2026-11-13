import { defineConfig, devices } from '@playwright/test'

// The tests run against a real stack (docker/docker-compose.e2e.yaml): panel -> nginx -> Omnixon -> Postgres.
// No test needs a working LLM key; where the service would call a model, the tests expect its 502.
export default defineConfig({
  testDir: './e2e',
  // One database is shared by every test, so they run one after another.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 800 },
        permissions: ['microphone'],
        launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] },
      },
    },
  ],
})
