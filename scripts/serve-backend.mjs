// scripts/serve-backend.mjs
// 启动重构后的 FastAPI 后端（backend/），供 npm run dev / npm run server 使用。
// - 自动定位 backend/.venv 里的 uvicorn（跨平台：posix 的 bin/ 与 win32 的 Scripts/）；
// - 以 backend/ 为工作目录启动，保证 pydantic-settings 能读到 backend/.env；
// - 默认监听 127.0.0.1:8000，多余参数原样透传给 uvicorn（如 --reload）。
//
// 历史：dev:server 原指向旧 Express 后端（server/index.js，端口 3001），该后端已退役删除。
// FastAPI 兼容层沿用旧接口契约，前端无需改动。
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backendDir = path.join(repoRoot, 'Workbench')
const venvDir = path.join(backendDir, '.venv')
const isWin = process.platform === 'win32'
const binDir = path.join(venvDir, isWin ? 'Scripts' : 'bin')
const exeSuffix = isWin ? '.exe' : ''

const uvicorn = path.join(binDir, `uvicorn${exeSuffix}`)
const python = path.join(binDir, `python${exeSuffix}`)
const envFile = path.join(backendDir, '.env')

const extra = process.argv.slice(2)

let command
let args
if (existsSync(uvicorn)) {
  command = uvicorn
  args = ['app.main:app', '--host', '127.0.0.1', '--port', '8000', ...extra]
} else if (existsSync(python)) {
  command = python
  args = ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', ...extra]
} else {
  console.error('[backend] 未找到 Workbench/.venv，请先初始化 Python 环境：')
  console.error('  cd Workbench && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt')
  process.exit(1)
}

if (!existsSync(envFile)) {
  console.warn(
    '[backend] 未找到 Workbench/.env：将使用内置默认配置（Workbench/data/app.db 全新空库）。' +
      '如需连接现有工作台数据库，请复制 Workbench/.env.example 为 Workbench/.env。'
  )
}

console.log(`[backend] 启动 FastAPI 后端：${command} ${args.join(' ')}`)
const child = spawn(command, args, { cwd: backendDir, stdio: 'inherit' })

child.on('error', (err) => {
  console.error(`[backend] 启动失败：${err.message}`)
  process.exit(1)
})
child.on('exit', (code, signal) => {
  process.exit(code ?? (signal ? 1 : 0))
})

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => child.kill(sig))
}
