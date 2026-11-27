import { randomUUID } from 'node:crypto'
import { expect, type APIRequestContext, type Page } from '@playwright/test'

export interface TestUser {
  readonly email: string
  readonly password: string
}

// The api asks for 8 to 72 characters.
const TEST_PASSWORD = 'an-e2e-test-password'
const CREATED = 201

// Registers a brand-new user straight through the api. Quicker and steadier
// than the form, and the tests that use it are about signing in, not about
// registering. A new email each time, because the dev database keeps its users.
export async function createUser(request: APIRequestContext): Promise<TestUser> {
  const user = { email: `e2e-${randomUUID()}@example.com`, password: TEST_PASSWORD }

  const response = await request.post('/api/auth/register', { data: user })

  // The body goes into the failure message, so a 409 or 422 says why.
  expect(response.status(), await response.text()).toBe(CREATED)
  return user
}

// Fills the login form and presses "Sign in". Waits for the form itself, so
// it can be called while the page still shows "Checking your sign-in…".
export async function signInWith(page: Page, email: string, password: string): Promise<void> {
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
}
