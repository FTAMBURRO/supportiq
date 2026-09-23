/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Flask dev server behind the proxy: /api stays same-origin in the
// browser, so development needs no CORS (and none is configured).
// Override with VITE_PROXY_TARGET when Flask runs elsewhere, e.g.
//   VITE_PROXY_TARGET=http://127.0.0.1:5000 npm run dev
const flaskTarget = process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:5001'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: flaskTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
