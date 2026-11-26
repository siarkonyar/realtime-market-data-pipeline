import { expect, test } from '@playwright/test'
import { createUser, signInWith } from './users'

test('a wrong password shows an error and stays on the login page', async ({ page, request }) => {
  const user = await createUser(request)
  await page.goto('/')

  await signInWith(page, user.email, 'not-the-right-password')

  // The api's 401, turned into words by LoginPage.
  await expect(page.getByRole('alert')).toHaveText('Wrong email or password.')
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()
})

test('the right password opens the dashboard', async ({ page, request }) => {
  const user = await createUser(request)
  await page.goto('/')

  await signInWith(page, user.email, user.password)

  // Only the dashboard's top bar has these two.
  await expect(page.getByText(user.email)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
})
