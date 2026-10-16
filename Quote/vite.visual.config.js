import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * 黄金屏渲染专用构建配置。
 *
 * 产出 IIFE + 独立 CSS，再由 capture.mjs 内联成**单个自包含 HTML**，
 * 用 file:// 直接截图 —— 不依赖本地 HTTP 服务（CI/沙箱环境下更稳）。
 * 与业务构建（vite.config.js）完全隔离，不影响 Electron 产物。
 */
export default defineConfig({
  root: resolve(process.cwd(), 'visual'),
  base: './',
  plugins: [vue()],
  // lib 模式下 Vite 不会替换 process.env.NODE_ENV（留给打包方处理），
  // 但我们要把产物当普通 script 在浏览器里跑，必须显式定义，否则 ReferenceError: process is not defined
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
    'process.env': '{}',
  },
  build: {
    outDir: resolve(process.cwd(), 'visual-dist'),
    emptyOutDir: true,
    cssCodeSplit: false,
    lib: {
      entry: resolve(process.cwd(), 'visual/main.js'),
      name: 'QuoteVisualHarness',
      formats: ['iife'],
      fileName: () => 'harness.js',
    },
  },
})
