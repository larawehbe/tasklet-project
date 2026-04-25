import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite proxies /api/* to the FastAPI backend on :8000.
// This means:
//   - the React app calls relative URLs like /api/users
//   - no CORS preflight, no env-specific URL handling
//   - production deploys can put both behind one host
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
