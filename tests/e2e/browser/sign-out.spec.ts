import { expect, test } from '@playwright/test'
import { createUser, signInWith } from './users'

// SESSION_COOKIE in api/auth.py.
const SESSION_COOKIE = 'session'

test('signing out deletes the session cookie, so a reload stays signed out', async ({ page, request }) => {
  const user = await createUser(request)
  await page.goto('/')
  await signInWith(page, user.email, user.password)

  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()

  // React cannot touch an httpOnly cookie; only the api's Max-Age=0 removes
  // it. The browser's own cookie list is the proof that it did.
  const cookieNames = (await page.context().cookies()).map((cookie) => cookie.name)
  expect(cookieNames).not.toContain(SESSION_COOKIE)

  // With the cookie still there, GET /auth/session would answer 200 and the
  // reload would open the dashboard again.
  await page.reload()
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()
})
