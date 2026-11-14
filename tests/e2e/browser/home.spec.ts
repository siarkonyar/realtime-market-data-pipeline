import { expect, test } from '@playwright/test'

test('the browser shows the React page', async ({ page }) => {
  await page.goto('/')

  // Only appears if the JavaScript bundle loaded and React drew the page.
  await expect(page.getByRole('heading', { name: 'Market data' })).toBeVisible()
})

test('the page calls the api on its own address, with no CORS', async ({ page }) => {
  await page.goto('/')

  // Runs inside the page, exactly like the app's own fetch calls will. A
  // cross-origin call would be blocked by the browser; this one goes through
  // nginx on the same address the page came from.
  const health = await page.evaluate(async () => {
    const response = await fetch('/api/health')
    return { status: response.status, body: await response.json() }
  })

  expect(health).toEqual({ status: 200, body: { status: 'ok' } })
})
