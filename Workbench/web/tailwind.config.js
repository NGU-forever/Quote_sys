/**
 * Tailwind 配置（工作台 renderer / designer 的样式基础）
 *
 * 重要：preflight 关闭。
 * 工作台既有界面样式由 src/shared/assets/main.css 手写维护（.wb-* / CSS 变量），
 * 打开 preflight 会重置标题、按钮、表格等基础样式，直接影响已有界面。
 * 这里只提供工具类，不动基础样式。
 *
 * 内容来源：从报价端 Quote/ 迁入的 designer + renderer（Spec 渲染与设计向导）。
 */
export default {
  content: [
    './workbench.html',
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
