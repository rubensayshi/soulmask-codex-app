import { createRequire } from 'node:module'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const require = createRequire(import.meta.url)
const { getDevPort } = require('./scripts/dev-port.cjs')

const host = process.env.TAURI_DEV_HOST
const port = getDevPort()

export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: {
    port,
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: 'ws', host, port: port + 1 } : undefined,
    watch: { usePolling: true },
  },
  envPrefix: ['VITE_', 'TAURI_'],
})
