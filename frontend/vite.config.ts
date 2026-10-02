/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  // The static site is relative to wherever it is uploaded (a sub-domain root or a folder).
  base: process.env.VITE_STATIC === 'true' ? './' : '/',
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
    env: { VITE_USE_MOCK: 'false', VITE_API_BASE_URL: 'http://localhost:8000' },
  },
})
