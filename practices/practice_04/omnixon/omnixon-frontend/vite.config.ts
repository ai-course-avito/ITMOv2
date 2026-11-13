import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// The service has no CORS, so the panel talks to it through a same-origin proxy:
// Vite in dev (below), nginx in the Docker image (see docker/nginx.conf.template).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.OMNIXON_URL || 'http://localhost:8083'
  const proxy = { target, changeOrigin: true }
  const ops = { ...proxy, rewrite: (p: string) => p.replace(/^\/_ops/, '') }
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
    server: {
      proxy: { '/api': proxy, '/_ops': ops },
    },
  }
})
