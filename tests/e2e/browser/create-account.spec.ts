import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'

// The dev database keeps its users between runs, so a fixed email would get
// "already exists" the second time. The api lower-cases emails; this one
// already is, so the top bar shows it exactly as typed.
const NEW_EMAIL = `e2e-${randomUUID()}@example.com`
// The api asks for 8 to 72 characters.
const NEW_PASSWORD = 'a-new-e2e-password'

test('a new user creates an account and lands on the dashboard', async ({ page }) => {
  await page.goto('/')

  // The page first shows "Checking your sign-in…". With no session cookie the
  // api answers 401 and the login page comes up.
  await page.getByRole('button', { name: 'Create one' }).click()

  // exact: true, or 'Password' would also match "Repeat password".
  await page.getByLabel('Email').fill(NEW_EMAIL)
  await page.getByLabel('Password', { exact: true }).fill(NEW_PASSWORD)
  await page.getByLabel('Repeat password').fill(NEW_PASSWORD)
  await page.getByRole('button', { name: 'Create account' }).click()

  // Only the dashboard's top bar has these two. Seeing them means register,
  // login and the session cookie all worked through nginx and the real api.
  await expect(page.getByText(NEW_EMAIL)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
})
