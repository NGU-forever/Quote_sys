#!/usr/bin/env node
/**
 * 黄金屏截图与基准比对。
 *
 *   node tests/visual/capture.mjs            # 重新渲染并与基准比对（CI 用）
 *   node tests/visual/capture.mjs --update   # 重新生成基准（渲染器/token 有意的改动）
 *   node tests/visual/capture.mjs --no-build # 跳过 vite 构建，直接用已有 visual-dist
 *
 * 覆盖矩阵：3 风格 × 5 骨架 = 15 张屏幕基准 + 3 张打印版式基准 = 18 张。
 *
 * 实现要点：把 IIFE bundle 与 CSS 内联成**单个自包含 HTML**，用 file:// 截图，
 * 不依赖本地 HTTP 服务 —— 在受限/CI 环境下更稳（Chrome 连 localhost 可能被拦）。
 */
import { execFileSync, spawnSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'

const ROOT = resolve(import.meta.dirname, '../..')
const DIST = join(ROOT, 'visual-dist')
const BASELINE = join(ROOT, 'visual', 'baseline')
const CURRENT = join(ROOT, 'visual', 'current')
const HARNESS_HTML = join(DIST, 'harness.html')
const UPDATE = process.argv.includes('--update')
const SKIP_BUILD = process.argv.includes('--no-build')

const SKELETONS = [
  'catalog-left-form-right',
  'form-first-wizard',
  'list-detail-split',
  'dashboard-grid',
  'mobile-single-column',
]
const PRESETS = ['medical-clean', 'industrial-dense', 'brand-premium']
const VIEWPORT = {
  'mobile-single-column': [390, 844],
  default: [1440, 900],
  print: [820, 1160],
}

function fail(message) {
  console.error(`\n[visual] ${message}`)
  process.exit(1)
}

function chromePath() {
  const candidates = [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
  ]
  return candidates.find((p) => p && existsSync(p))
}

function pythonPath() {
  if (process.env.VISUAL_PYTHON) return process.env.VISUAL_PYTHON
  const hasPillow = (bin) => spawnSync(bin, ['-c', 'import PIL'], { stdio: 'ignore' }).status === 0
  if (hasPillow('python3')) return 'python3'
  const bundled = join(
    process.env.HOME || '',
    '.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3'
  )
  if (existsSync(bundled) && hasPillow(bundled)) return bundled
  return 'python3'
}

function buildHarness() {
  console.log('[visual] 构建渲染 harness …')
  // 直接调用本地 vite 二进制：npx 在本机可能解析到其它副本，且会受 ~/.npm 权限影响
  const viteBin = join(ROOT, 'node_modules', 'vite', 'bin', 'vite.js')
  if (!existsSync(viteBin)) fail(`未找到本地 vite：${viteBin}（请先在 Quote/ 下执行 npm install）`)
  const result = spawnSync(process.execPath, [viteBin, 'build', '--config', 'vite.visual.config.js'], {
    cwd: ROOT,
    stdio: 'inherit',
    shell: false,
  })
  if (result.status !== 0) fail('harness 构建失败')
}

function buildSelfContainedHtml() {
  const cssPath = join(DIST, 'style.css')
  const jsPath = join(DIST, 'harness.js')
  if (!existsSync(jsPath)) fail(`缺少构建产物：${jsPath}`)
  const css = existsSync(cssPath) ? readFileSync(cssPath, 'utf8') : ''
  const js = readFileSync(jsPath, 'utf8')
  const html = `<!doctype html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>QuoteSys 黄金屏</title><style>${css}</style></head>
<body><div id="app"></div><script>${js}</script></body>
</html>`
  writeFileSync(HARNESS_HTML, html, 'utf8')
}

function shoot(chrome, url, outPath, [width, height], profileDir) {
  execFileSync(
    chrome,
    [
      '--headless=new',
      '--disable-gpu',
      // 受限环境下 Chrome 需要关闭自身沙箱，否则会 SIGTRAP
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--disable-extensions',
      '--hide-scrollbars',
      '--no-first-run',
      '--no-default-browser-check',
      '--force-device-scale-factor=1',
      `--user-data-dir=${profileDir}`,
      `--window-size=${width},${height}`,
      `--screenshot=${outPath}`,
      url,
    ],
    // 单张超时保护：Chrome 偶发挂起时不要拖垮整条流水线
    { stdio: 'ignore', timeout: Number(process.env.VISUAL_SHOT_TIMEOUT_MS || 45000) }
  )
  if (!existsSync(outPath)) fail(`截图未生成：${outPath}`)
}

function targets() {
  const list = []
  for (const skeleton of SKELETONS) {
    for (const preset of PRESETS) {
      list.push({
        name: `${skeleton}__${preset}.png`,
        query: `?skeleton=${skeleton}&preset=${preset}`,
        viewport: VIEWPORT[skeleton] || VIEWPORT.default,
      })
    }
  }
  for (const preset of PRESETS) {
    list.push({
      name: `print__${preset}.png`,
      query: `?skeleton=catalog-left-form-right&preset=${preset}&print=1`,
      viewport: VIEWPORT.print,
    })
  }
  return list
}

function main() {
  const chrome = chromePath()
  if (!chrome) {
    console.error('[visual] 未找到 Chrome/Chromium。可设置 CHROME_PATH 指定可执行文件。')
    process.exit(2)
  }
  if (!SKIP_BUILD) buildHarness()
  buildSelfContainedHtml()

  rmSync(CURRENT, { recursive: true, force: true })
  mkdirSync(CURRENT, { recursive: true })
  // Chrome profile 放在系统临时目录：避免污染仓库，也避开工作区写权限限制
  const profileDir = mkdtempSync(join(tmpdir(), 'qs-visual-'))

  const shots = targets()
  console.log(`[visual] 截图中：${shots.length} 张（Chrome: ${chrome}）`)
  for (const shot of shots) {
    shoot(chrome, `file://${HARNESS_HTML}${shot.query}`, join(CURRENT, shot.name), shot.viewport, profileDir)
    console.log(`  ✓ ${shot.name}`)
  }
  rmSync(profileDir, { recursive: true, force: true })

  if (UPDATE) {
    rmSync(BASELINE, { recursive: true, force: true })
    mkdirSync(BASELINE, { recursive: true })
    cpSync(CURRENT, BASELINE, { recursive: true })
    console.log(`\n[visual] 基准已更新：${BASELINE}（${shots.length} 张）`)
    return
  }

  const compare = spawnSync(pythonPath(), [join(ROOT, 'tests', 'visual', 'compare.py')], {
    stdio: 'inherit',
    cwd: ROOT,
  })
  process.exit(compare.status ?? 1)
}

main()
