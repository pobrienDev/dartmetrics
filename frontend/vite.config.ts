import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Forward API calls to the FastAPI backend so the browser sees one
    // origin — no CORS configuration needed during development.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // Globals let React Testing Library auto-clean the DOM between tests
    globals: true,
    // e2e/ belongs to Playwright, not Vitest
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
