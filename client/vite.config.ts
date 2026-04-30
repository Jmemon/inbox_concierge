import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

const OUT_DIR = process.env.VITE_OUT_DIR
  ? path.resolve(process.env.VITE_OUT_DIR)
  : path.resolve(__dirname, '../server/app/static')

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: OUT_DIR,
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
    },
  },
})
