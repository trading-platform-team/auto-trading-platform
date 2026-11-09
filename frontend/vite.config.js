import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // 로컬 개발 시 /api 요청을 백엔드로 전달
    proxy: { '/api': { target: 'http://localhost:8000', ws: true, rewrite: (p) => p.replace(/^\/api/, '') } },
  },
})
