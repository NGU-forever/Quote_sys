/**
 * Tailwind 配置（renderer / designer 的样式基础）
 *
 * 重要：preflight 关闭。
 * 本仓库既有的界面样式由 src/shared/assets/main.css 手写维护（.btn / .badge 等），
 * 打开 preflight 会重置标题、按钮、表格等基础样式，直接影响已有界面。
 * 这里只提供工具类，不动基础样式。
 */
export default {
  content: [
    './index.html',
    './visual/**/*.{html,js,vue}',
    './src/**/*.{vue,js}',
  ],
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {},
  },
  plugins: [],
}
