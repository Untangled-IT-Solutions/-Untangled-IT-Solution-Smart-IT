import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The Website uses the Node backend. Nexus has its own FastAPI deployment.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const websiteApiTarget = (env.WEBSITE_API_PROXY_TARGET || 'http://localhost:5001').trim()
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: websiteApiTarget,
          changeOrigin: true,
          secure: true,
        },
      },
    },
  }
})
