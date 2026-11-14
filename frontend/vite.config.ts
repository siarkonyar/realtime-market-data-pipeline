/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The unit tests live with every other test, in tests/unit/frontend, not in
// this folder. The settings marked (tests) let Vite and Vitest reach them.
const TESTS_DIR = '../tests/unit/frontend'

export default defineConfig({
  plugins: [react()],
  resolve: {
    // (tests) A package is looked up in the node_modules above the file that
    // imports it, and a test file has none. These are looked up here instead.
    // Add any new package a test imports directly.
    dedupe: ['react', 'react-dom', '@testing-library/react', '@testing-library/jest-dom'],
  },
  server: {
    // (tests) Vite refuses to read files outside frontend/ unless allowed.
    fs: { allow: ['.', TESTS_DIR] },
  },
  test: {
    dir: TESTS_DIR,
    environment: 'jsdom',
    setupFiles: [`${TESTS_DIR}/setup.ts`],
  },
})
