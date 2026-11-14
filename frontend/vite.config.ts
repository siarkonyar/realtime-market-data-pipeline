/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, type ProxyOptions } from 'vite'

// The unit tests live with every other test, in tests/unit/frontend, not in
// this folder. The settings marked (tests) let Vite and Vitest reach them.
const TESTS_DIR = '../tests/unit/frontend'

// docker-compose.yaml publishes the api on this port.
const API_HOST = 'localhost:8000'

// `npm run dev` only. Vite passes these requests on to the api, the same way
// nginx does in the container, so the page only ever talks to its own address.
export const devProxy = {
  // The api has /candles, not /api/candles, so the /api is cut off first.
  '/api': {
    target: `http://${API_HOST}`,
    rewrite: (path: string) => path.replace(/^\/api/, ''),
  },
  // The api route itself is /ws/candles, so this prefix stays.
  '/ws': { target: `ws://${API_HOST}`, ws: true },
} satisfies Record<string, ProxyOptions>

export default defineConfig({
  plugins: [react()],
  resolve: {
    // (tests) A package is looked up in the node_modules above the file that
    // imports it, and a test file has none. These are looked up here instead.
    // Add any new package a test imports directly.
    dedupe: ['react', 'react-dom', '@testing-library/react', '@testing-library/jest-dom'],
  },
  server: {
    proxy: devProxy,
    // (tests) Vite refuses to read files outside frontend/ unless allowed.
    fs: { allow: ['.', TESTS_DIR] },
  },
  test: {
    dir: TESTS_DIR,
    environment: 'jsdom',
    setupFiles: [`${TESTS_DIR}/setup.ts`],
  },
})
