// scripts/build-backend-exe.mjs
// 构建后端「QuoteService.exe」（Windows 托盘后台服务），跨平台一键执行：
//
//   Windows（原生，推荐）:
//     本脚本直接委托 scripts\build-backend.bat（前端构建 → 安装依赖 → pyinstaller → 复制到 release\）。
//
//   macOS / Linux（Docker + Wine 容器，Apple Silicon 走 amd64 模拟，首次较慢）:
//     1. 确保已构建前端 dist/workbench.html（缺失时自动执行 npm run build）；
//     2. 启动 batonogov/pyinstaller-windows（Ubuntu + Wine + Windows Python 3.13 + PyInstaller 6.x）,
//        把仓库挂载到容器 /src，容器内自动 `pip install -r Workbench/requirements.txt` 并
//        `pyinstaller Workbench/quote-service.spec`；
//     3. 把产物复制到 release/QuoteService.exe 并清理临时 dist。
//
// 依赖：Node 18+；macOS/Linux 额外需要 Docker（首次自动拉取 ~1.5GB 镜像）。
//
// 用法：
//   node scripts/build-backend-exe.mjs
//   PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple node scripts/build-backend-exe.mjs  # 换 pip 源
import { spawnSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const isWin = process.platform === 'win32'
const exeName = 'QuoteService.exe'
const seedDb = path.join(repoRoot, 'Workbench', 'data', 'app.db')
const IMAGE = 'batonogov/pyinstaller-windows:latest'

function fail(msg) {
  console.error(`\n[build-backend] ${msg}`)
  process.exit(1)
}

if (existsSync(seedDb)) {
  console.log('[build-backend] 将把 Workbench/data/app.db 作为初始数据打入 exe。')
} else {
  console.warn(
    '[build-backend] 未找到 Workbench/data/app.db，本次打包不带当前本地数据库；' +
      '若需随包分发数据，请先把目标 app.db 放到 Workbench/data/ 后重试。'
  )
}

// ---------- Windows：委托原生 bat ----------
if (isWin) {
  console.log('[build-backend] Windows 平台：委托 scripts\\build-backend.bat 原生构建…')
  const r = spawnSync('cmd', ['/c', path.join('scripts', 'build-backend.bat')], {
    cwd: repoRoot,
    stdio: 'inherit',
    shell: false
  })
  process.exit(r.status ?? 1)
}

// ---------- macOS / Linux：Docker + Wine ----------
console.log(
  '[build-backend] 非 Windows 平台：走 Docker + Wine 容器构建（PyInstaller 不支持跨平台）。'
)

// 1. 前置检查：docker
const dockerCheck = spawnSync('docker', ['version', '--format', '{{.Server.Version}}'], {
  encoding: 'utf8'
})
if (dockerCheck.status !== 0) {
  fail(
    '未检测到可用的 Docker。\n' +
      '  后端 exe 只能由 Windows Python 产出，本机请任选其一：\n' +
      '  1) 在任意 Windows 机器执行 scripts\\build-backend.bat（原生，推荐）；\n' +
      '  2) 在本机安装并启动 Docker Desktop 后重试本脚本（首次自动拉取 wine 镜像，约 1.5GB）。'
  )
}

// 2. 确保前端工作台已构建（exe 内嵌 dist/workbench.html + assets）
const webDir = path.join(repoRoot, 'Workbench', 'web')
const workbenchHtml = path.join(webDir, 'dist', 'workbench.html')
if (!existsSync(workbenchHtml)) {
  console.log('[build-backend] 未发现 Workbench/web/dist/workbench.html，先执行 npm run build …')
  const b = spawnSync('npm', ['run', 'build'], { cwd: webDir, stdio: 'inherit' })
  if (b.status !== 0) fail('npm run build 失败，请先手动修复工作台前端构建。')
} else {
  console.log('[build-backend] Workbench/web/dist/workbench.html 已存在，复用现有构建产物。')
}

// 3. 清理上次产物，避免旧 exe 残留
const backendDist = path.join(repoRoot, 'Workbench', 'dist')
const releaseDir = path.join(repoRoot, 'release')
rmSync(backendDist, { recursive: true, force: true })
mkdirSync(releaseDir, { recursive: true })

// 4. 容器构建：仓库挂载到 /src，SRCDIR 指向 Workbench，自动读 requirements.txt 与 spec
const env = { ...process.env }
// 可选 pip 镜像（容器内 wine python 读 PYPI_INDEX_URL / PYPI_URL）
const dockerArgs = [
  'run',
  '--rm',
  '--platform',
  'linux/amd64',
  '-v',
  `${repoRoot}:/src`,
  '-e',
  'SRCDIR=/src/Workbench'
]
if (env.PYPI_INDEX_URL) dockerArgs.push('-e', 'PYPI_INDEX_URL')
if (env.PYPI_URL) dockerArgs.push('-e', 'PYPI_URL')
dockerArgs.push(IMAGE)

console.log(`[build-backend] docker ${dockerArgs.join(' ')}`)
const run = spawnSync('docker', dockerArgs, { cwd: repoRoot, stdio: 'inherit', env })
if (run.status !== 0) {
  fail(
    `容器构建失败（exit=${run.status}）。常见原因：镜像首次拉取超时、网络无法访问 pypi（可设 PYPI_INDEX_URL 走国内源）。`
  )
}

// 5. 收尾：复制 exe → release/，清理临时 backend/dist
const built = path.join(backendDist, exeName)
if (!existsSync(built)) {
  fail(`构建结束但未找到 ${built}，请检查容器日志。`)
}
copyFileSync(built, path.join(releaseDir, exeName))
rmSync(backendDist, { recursive: true, force: true })
console.log(`[build-backend] 完成：${path.join(releaseDir, exeName)}`)

// 6. 可选：生成 NSIS 安装器（安装时自动放行防火墙 TCP 8000）。
//    找不到 makensis 时该脚本会打印提示并以 0 退出，不影响绿色版 exe 产物。
const installer = spawnSync(
  process.execPath,
  [path.join(repoRoot, 'scripts', 'build-backend-installer.mjs')],
  { stdio: 'inherit' }
)
if (installer.status !== 0) {
  fail(`NSIS 安装器生成失败（exit=${installer.status}），请先修复后重试。`)
}
