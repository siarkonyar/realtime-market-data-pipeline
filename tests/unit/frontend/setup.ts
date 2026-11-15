// Runs before every test file (see test.setupFiles in frontend/vite.config.ts).
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Testing Library only cleans up by itself when Vitest globals are on. They
// are off here, so without this each test would see the last test's page.
afterEach(() => {
  cleanup()
})
