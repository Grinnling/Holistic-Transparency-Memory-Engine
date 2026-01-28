import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on mode (development, production, etc.)
  const env = loadEnv(mode, process.cwd(), '')

  // Get API URL from environment with fallback
  const apiUrl = env.VITE_API_URL || 'http://localhost:8000'
  // Convert http:// to ws:// for WebSocket proxy
  const wsUrl = apiUrl.replace(/^http/, 'ws')

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: parseInt(env.VITE_PORT || '3000'),
      proxy: {
        '/api': {
          target: apiUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, '')
        },
        '/ws': {
          target: wsUrl,
          ws: true
        }
      }
    }
  }
})
