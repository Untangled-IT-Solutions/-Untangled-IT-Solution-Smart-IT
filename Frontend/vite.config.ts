import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev: browser calls same-origin /api → Vite proxies to Render (avoids CORS)
const RENDER_API = 'https://untangled-nexus-api.onrender.com'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: RENDER_API,
        changeOrigin: true,
        secure: true,
      },
    },
  },
})
