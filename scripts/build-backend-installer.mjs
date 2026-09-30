// scripts/build-backend-installer.mjs
// 用 NSIS 把 release/HHZDataService.exe 包成安装器
//   release/HHZDataService Setup <版本>.exe
// 安装器会在安装时自动放行 Windows 防火墙 TCP 8000（专用网络），无需关闭防火墙。
//
// 用法：
//   node scripts/build-backend-exe.mjs        # Windows 原生 / macOS·Linux Docker 之后自动附带
//   node scripts/build-backend-installer.mjs
//   APP_VERSION=2.0.0 node scripts/build-backend-installer.mjs   # 覆盖版本号（默认读 Quote/package.json）
//
// makensis 定位顺序：
//   1. PATH 中的 makensis（系统安装的 NSIS，推荐：winget install NSIS.NSIS）
//   2. 仓库 .electron-cache/nsis/nsis-*/（electron-builder 缓存，mac/linux/win 平台二进制）
//   3. 平台默认 electron-builder 缓存目录（mac: ~/Library/Caches/electron-builder）
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const srcExe = path.join(repoRoot, 'release', 'HHZDataService.exe')

function fail(msg) {
  console.error(`\n[backend-installer] ${msg}`)
  process.exit(1)
}

// ---------- 版本号 ----------
// 优先级：APP_VERSION 环境变量 > 根目录 package.json（兼容旧用法）> Quote/package.json > 默认 2.0.0。
// 两系统拆分后包清单在 Quote/package.json，读不到时不再崩溃。
let pkgVersion = null
for (const rel of ['package.json', path.join('Quote', 'package.json')]) {
  try {
    pkgVersion = JSON.parse(readFileSync(path.join(repoRoot, rel), 'utf8')).version
    if (pkgVersion) break
  } catch {}
}
const version = process.env.APP_VERSION || pkgVersion || '2.0.0'
const setupFile = path.join(repoRoot, 'release', `HHZDataService Setup ${version}.exe`)

// ---------- 前置：源 exe 必须已构建 ----------
if (!existsSync(srcExe)) {
  fail(
    `未找到 ${srcExe}。\n` +
      '  请先产出后端 exe：Windows 上执行 scripts\\build-backend.bat，或 macOS/Linux 执行 node scripts/build-backend-exe.mjs（Docker）。'
  )
}

// ---------- 定位 makensis ----------
function platformName() {
  if (process.platform === 'win32') return 'win'
  if (process.platform === 'darwin') return 'mac'
  return 'linux'
}

function walkVersionDirs(cacheNsisDir) {
  // 每个版本子目录形如 nsis-3.0.4.1/，其下含 Include、Plugins、Stubs 与平台二进制。
  if (!existsSync(cacheNsisDir)) return []
  return readdirSync(cacheNsisDir)
    .map((d) => path.join(cacheNsisDir, d))
    .filter((d) => existsSync(path.join(d, 'Include')) && existsSync(path.join(d, 'Stubs')))
}

function candidateRoots() {
  const roots = []
  const cacheDirs = [
    path.join(repoRoot, '.electron-cache', 'nsis'),
    path.join(
      os.homedir(),
      process.platform === 'win32'
        ? path.join('AppData', 'Local', 'electron-builder', 'Cache', 'nsis')
        : process.platform === 'darwin'
          ? path.join('Library', 'Caches', 'electron-builder', 'nsis')
          : path.join('.cache', 'electron-builder', 'nsis')
    )
  ]
  for (const dir of cacheDirs) roots.push(...walkVersionDirs(dir))
  return roots
}

function makensisUnder(root) {
  // 各缓存布局：mac/makensis、linux/makensis、Bin/makensis.exe（Win 亦同）。
  const p = platformName()
  const rels =
    p === 'win'
      ? ['Bin/makensis.exe', 'makensis.exe']
      : p === 'mac'
        ? ['mac/makensis', 'Bin/makensis.exe']
        : ['linux/makensis']
  for (const rel of rels) {
    const bin = path.join(root, rel)
    if (existsSync(bin)) return bin
  }
  return null
}

// 探测 makensis 可用性并确定需要哪种环境：
//   - 'builtin'：系统安装版（brew/winget 官方包），自带数据目录，不要设 NSISDIR
//   - 'nsisdir'：缓存布局（.electron-cache / electron-builder 缓存），需 NSISDIR=<nsis 根>
// 返回 null 表示不可用。
function works(bin, root) {
  const tryRun = (env) =>
    spawnSync(bin, ['-VERSION'], { env: { ...process.env, ...env }, encoding: 'utf8', stdio: 'pipe' })
      .status === 0
  if (tryRun({})) return 'builtin'
  if (root && tryRun({ NSISDIR: root })) return 'nsisdir'
  return null
}

function resolveMakensis() {
  // 1) PATH 上的 makensis（系统安装版）
  const onPath = spawnSync(process.platform === 'win32' ? 'where' : 'which', ['makensis'], {
    encoding: 'utf8'
  })
  if (onPath.status === 0 && onPath.stdout.trim()) {
    const bin = onPath.stdout.trim().split(/\r?\n/)[0].trim()
    const mode = works(bin, path.dirname(bin))
    if (mode) return { bin, root: path.dirname(bin), mode }
  }

  // 2) 各缓存版本目录中的平台二进制
  for (const root of candidateRoots()) {
    const bin = makensisUnder(root)
    if (bin) {
      const mode = works(bin, root)
      if (mode) return { bin, root, mode }
    }
  }
  return null
}

const makensis = resolveMakensis()
if (!makensis) {
  console.warn(
    '\n[backend-installer] 未找到可用的 makensis（NSIS 编译器），跳过安装器生成（release 中仍有绿色版 HHZDataService.exe）。\n' +
      '  生成安装器请任选其一：\n' +
      '  1) Windows 安装 NSIS 后重跑：winget install NSIS.NSIS\n' +
      '  2) 本机 electron-builder 缓存（.electron-cache/nsis 或系统缓存目录）中已有 NSIS 时会自动使用\n' +
      '  3) macOS: brew install nsis\n'
  )
  process.exit(0) // 绿色版 exe 仍是有效产物，仅提示
}

// ---------- 编译 ----------
console.log(`[backend-installer] makensis: ${makensis.bin}（${makensis.mode === 'nsisdir' ? '缓存布局' : '系统安装'}）`)
console.log(`[backend-installer] 版本 ${version} → ${setupFile}`)
const nsisEnv =
  makensis.mode === 'nsisdir' ? { ...process.env, NSISDIR: makensis.root } : { ...process.env }
const r = spawnSync(
  makensis.bin,
  [
    `-DAPP_VERSION=${version}`,
    `-DSRC_EXE=${srcExe}`,
    `-DSETUP_FILE=${setupFile}`,
    path.join(repoRoot, 'scripts', 'backend-installer.nsi')
  ],
  { env: nsisEnv, stdio: 'inherit' }
)
if (r.status !== 0) {
  fail(`NSIS 编译失败（exit=${r.status}）。`)
}
if (!existsSync(setupFile)) {
  fail('NSIS 编译结束但未找到安装器产物。')
}
console.log(`[backend-installer] 完成：${setupFile}`)
