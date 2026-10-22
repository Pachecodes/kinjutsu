import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

/**
 * The production bundle is served by FastAPI out of `frontend/dist`, so the
 * build stays relative-free (`base: '/'`) and the dev server proxies `/api`
 * straight to the loopback Studio backend on :8220.
 */
export default defineConfig({
  plugins: [react()],
  base: '/',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        // H3_STUDIO_API points the dev proxy at another local Studio (e.g. :8221) without editing this file.
        target: process.env.H3_STUDIO_API ?? 'http://127.0.0.1:8220',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
})
