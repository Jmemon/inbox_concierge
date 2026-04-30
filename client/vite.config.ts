import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// Build outputs land inside the python package so FastAPI's StaticFiles mount picks them up.
const OUT_DIR = path.resolve(__dirname, '../server/app/static')

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
