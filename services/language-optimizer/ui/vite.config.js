import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',          // ← relative paths so assets work from any URL
  build: { outDir: 'build' },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/config.json': 'http://localhost:8000',
    }
  }
})
