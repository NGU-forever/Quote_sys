import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 工作台前端（主系统）：单入口 workbench.html，构建产物 dist/workbench.html 由后端（Workbench/）托管。
// 后端 API 目标：本机 FastAPI（Workbench/，端口 8000，由 scripts/serve-backend.mjs 启动）。
const backendTarget = process.env.BACKEND_TARGET || 'http://localhost:8000'

export default defineConfig({
  base: './',
  plugins: [vue()],
  build: {
    rollupOptions: {
      input: {
        workbench: resolve(process.cwd(), 'workbench.html')
      }
    }
  },
  server: {
    host: true,
    port: 5174,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true
      },
      '/uploads': {
        target: backendTarget,
        changeOrigin: true
      }
    }
  }
})
