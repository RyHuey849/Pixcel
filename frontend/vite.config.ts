import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The FastAPI dev server. Only referenced here - see the proxy note below.
const BACKEND_URL = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // DESIGN DECISION: proxy /api to the backend instead of calling it by
    // absolute URL from the React code. The app then only ever fetches
    // same-origin relative paths, which means no CORS preflight in development
    // and no backend host baked into the bundle - in production the same /api
    // paths are served by whatever host the app is deployed behind.
    proxy: {
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
})
