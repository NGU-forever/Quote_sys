// scripts/dev.mjs
// 开发模式（热更新）：启动 Vite dev server，并让 Electron 加载该地址。
// 修改 Quote/src 下的代码（Vue/JS/CSS）会即时热更新，无需手动刷新或重新构建。
// 用法：npm run dev:desktop（在 Quote/ 下执行）
//
// 注意：本脚本位于仓库根 scripts/（该目录无独立 node_modules），而 vite / electron
// 依赖装在 Quote/ 下。若直接 import 'vite'，Node 会从 scripts/ 向上逐级找 node_modules
// 而失败（ERR_MODULE_NOT_FOUND）。因此这里用 createRequire 锚定 Quote/ 解析出依赖的
// 真实入口文件，再以 file:// URL 方式 import，绕开裸说明符的解析路径问题。
import { spawn } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const quoteDir = path.join(repoRoot, 'Quote')
const quoteRequire = createRequire(path.join(quoteDir, 'package.json'))

/** 沿着 exports 条件对象取到最终的字符串入口（跳过 types 等描述键，default 兜底）。 */
function pickExportEntry(node) {
  if (typeof node === 'string') return node
  if (!node || typeof node !== 'object') return null
  if (typeof node.default === 'string') return node.default
  for (const value of Object.values(node)) {
    const hit = pickExportEntry(value)
    if (hit) return hit
  }
  return null
}

/** 解析 Quote/node_modules 中某依赖的真实入口，返回可被 import() 的 file:// URL。
 *  优先走 package.json exports['.'] 的 import 条件（ESM），否则回退 main 字段。 */
function resolveFromQuote(pkgName) {
  const pkgJsonPath = quoteRequire.resolve(`${pkgName}/package.json`)
  const pkg = JSON.parse(readFileSync(pkgJsonPath, 'utf8'))
  const exportsDot = pkg.exports?.['.']
  const entry =
    pickExportEntry(exportsDot && typeof exportsDot === 'object' ? exportsDot.import : exportsDot) ||
    pickExportEntry(exportsDot) ||
    pkg.main ||
    'index.js'
  return pathToFileURL(path.join(path.dirname(pkgJsonPath), entry)).href
}

const port = Number(process.env.PORT) || 5173

// vite 走 package.json exports 的 import 条件（ESM 入口）；electron 无 exports，取 main
// （index.js，CJS，default 即 exe 路径）
const { createServer } = await import(resolveFromQuote('vite'))
const { default: electronPath } = await import(resolveFromQuote('electron'))

const server = await createServer({
  root: quoteDir, // 显式指定，保证无论从哪个目录启动都读 Quote/vite.config.js
  server: {
    port,
    host: true
  }
})
await server.listen()

const address = server.httpServer?.address()
const actualPort = typeof address === 'object' && address ? address.port : port
const url = `http://localhost:${actualPort}`
console.log(`[dev] Vite dev server: ${url}（修改 src 代码将即时热更新，无需手动刷新）`)

const electron = spawn(electronPath, ['.'], {
  cwd: quoteDir, // electron . 以 Quote/ 为应用目录（main: electron/main.cjs）
  env: { ...process.env, VITE_DEV_SERVER_URL: url },
  stdio: 'inherit'
})

// Electron 二进制缺失/损坏（如 node_modules 里 postinstall 未下载完成）时优雅退出，
// 不要抛未捕获的 'error' 事件把进程带崩。
electron.on('error', (err) => {
  console.error(`[dev] 无法启动 Electron：${err.message}`)
  console.error('[dev] 提示：electron 包未下载完整二进制，请重装依赖：')
  console.error(`[dev]   cd Quote && npm rebuild electron  （或删除 Quote/node_modules/electron 后 npm install）`)
  shutdown(1)
})

let closed = false
function shutdown(code = 0) {
  if (closed) return
  closed = true
  if (!electron.killed) electron.kill()
  server.close()
  process.exit(code)
}

electron.on('exit', (code) => {
  console.log(`[dev] Electron 已退出（code=${code}），关闭 Vite dev server`)
  shutdown(code ?? 0)
})

process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))
