import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // In production (Vercel), VITE_API_URL points to the Railway API.
  // In development, fall back to the local Docker API via proxy.
  const apiTarget = env.VITE_API_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: path => path.replace(/^\/api/, '')
        }
      }
    }
  }
})
