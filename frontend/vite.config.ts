import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const API_PROXY = {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
}

export default defineConfig({
  plugins: [react()],
  // Proxy /api to the FastAPI server so the browser sees a single origin.
  // Keeps the client free of base-URL configuration, and means a CORS
  // misconfiguration can't be mistaken for a broken query.
  //
  // `server` (dev) and `preview` (built output) are configured separately —
  // preview does NOT inherit server.proxy, so omitting the second block would
  // break every API call in `npm start`.
  server: {
    port: 3000,
    proxy: API_PROXY,
  },
  preview: {
    port: 4173,
    proxy: API_PROXY,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.ts',
  },
})
