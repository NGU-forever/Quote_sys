import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 报价版前端（副系统/客户机）：单入口 index.html，Electron 加载 dist/index.html。
// 后端 API 目标：FastAPI 主系统（Workbench/，端口 8000，由 npm run dev:server 启动）。
// 可用环境变量 BACKEND_TARGET 覆盖，例如：BACKEND_TARGET=http://localhost:9000 npm run dev
const backendTarget = process.env.BACKEND_TARGET || 'http://localhost:8000'

export default defineConfig({
  base: './',
  plugins: [vue()],
  // 显式指定入口，避免依赖扫描时 glob('**/*.html') 顺着
  // .electron-cache/wine 的 dosdevices/z: -> / 符号链接递归整个文件系统导致卡死
  optimizeDeps: {
    entries: ['index.html']
  },
  build: {
    rollupOptions: {
      input: {
        index: resolve(process.cwd(), 'index.html')
      }
    }
  },
  server: {
    host: true,
    port: 5173,
    open: true,
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
