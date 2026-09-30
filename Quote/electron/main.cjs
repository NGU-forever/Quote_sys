const { app, BrowserWindow, shell, ipcMain, protocol, net } = require('electron')
const path = require('node:path')
const os = require('node:os')
const fs = require('node:fs')

const devServerUrl = process.env.VITE_DEV_SERVER_URL

// 产品图片本地缓存目录：<userData>/image-cache
function imageCacheDir() {
  return path.join(app.getPath('userData'), 'image-cache')
}

// 安全拼接：确保解析后的路径仍在缓存根目录内，防止路径穿越
function safeJoin(root, rel) {
  const target = path.resolve(root, rel)
  if (target !== root && !target.startsWith(root + path.sep)) {
    throw new Error('非法路径')
  }
  return target
}

// 注册自定义协议 app-img://cache/<相对路径>，从本地缓存目录读取图片
// （渲染进程沙箱内无法直接加载 file://，用自定义协议最稳妥）
protocol.registerSchemesAsPrivileged([
  { scheme: 'app-img', privileges: { standard: true, secure: true, supportFetchAPI: true } }
])

const MIME = {
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.gif': 'image/gif'
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    title: '超声医疗报价平台',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, 'preload.cjs')
    }
  })

  if (devServerUrl) {
    win.loadURL(devServerUrl)
  } else {
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

/**
 * 从后端同步产品图片到本地缓存（单向拉取覆盖，绝不反向写回服务器）。
 * 1. 请求后端 GET /api/uploads/manifest 获取图片清单（含 size / mtime）；
 * 2. 对比本地缓存（.manifest.json 记录上次元数据），只下载新增/变更的文件；
 * 3. 清理本地已不在清单内的多余缓存；
 * 4. 返回 { ok, total, downloaded, skipped, failed, files }（files = 已就绪的本地相对路径）。
 */
async function syncImages(backendBase) {
  const base = String(backendBase || '').replace(/\/+$/, '')
  if (!base) return { ok: false, error: '未配置后端地址' }

  const cacheRoot = imageCacheDir()
  fs.mkdirSync(cacheRoot, { recursive: true })

  // 1. 拉取清单
  let manifest
  try {
    const res = await net.fetch(`${base}/api/uploads/manifest`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const body = await res.json()
    manifest = Array.isArray(body.data) ? body.data : []
  } catch (err) {
    return { ok: false, error: `无法获取图片清单：${err.message}` }
  }

  // 2. 读取上次同步元数据
  const metaFile = path.join(cacheRoot, '.manifest.json')
  let prev
  try {
    prev = JSON.parse(fs.readFileSync(metaFile, 'utf8'))
  } catch {
    prev = {}
  }

  // 3. 逐文件下载缺失/变更
  const files = []
  const failed = []
  let downloaded = 0
  for (const item of manifest) {
    const rel = String(item.path || '')
    if (!rel) continue
    const local = safeJoin(cacheRoot, rel)
    const prevMeta = prev[rel]
    const changed =
      !prevMeta ||
      prevMeta.size !== item.size ||
      Math.abs((prevMeta.mtime || 0) - (item.mtime || 0)) > 1
    if (!changed && fs.existsSync(local)) {
      files.push(rel)
      continue
    }
    try {
      const dres = await net.fetch(`${base}/uploads/${rel}`)
      if (!dres.ok) {
        failed.push(rel)
        continue
      }
      const buf = Buffer.from(await dres.arrayBuffer())
      fs.mkdirSync(path.dirname(local), { recursive: true })
      fs.writeFileSync(local, buf)
      files.push(rel)
      downloaded += 1
    } catch {
      failed.push(rel)
    }
  }

  // 4. 清理本地多余缓存（清单已不存在的文件）
  const keep = new Set(files)
  const walk = (dir) => {
    let entries
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true })
    } catch {
      return
    }
    for (const entry of entries) {
      const abs = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        walk(abs)
        try {
          if (fs.readdirSync(abs).length === 0) fs.rmdirSync(abs)
        } catch {
          /* ignore */
        }
      } else if (entry.name !== '.manifest.json') {
        const rel = path.relative(cacheRoot, abs).split(path.sep).join('/')
        if (!keep.has(rel)) {
          try {
            fs.unlinkSync(abs)
          } catch {
            /* ignore */
          }
        }
      }
    }
  }
  walk(cacheRoot)

  // 5. 写回元数据
  const next = {}
  for (const item of manifest) {
    next[item.path] = { size: item.size, mtime: item.mtime }
  }
  try {
    fs.writeFileSync(metaFile, JSON.stringify(next))
  } catch {
    /* ignore */
  }

  return {
    ok: true,
    total: manifest.length,
    downloaded,
    skipped: files.length - downloaded,
    failed,
    files
  }
}

// 目录本地缓存文件：<userData>/catalog-cache.json（/api/sync 结果，离线兜底）
function catalogCacheFile() {
  return path.join(app.getPath('userData'), 'catalog-cache.json')
}

/**
 * 收集本机所有非回环 IPv4 地址，按优先级排序：
 * 优先 Wi-Fi / 以太网等真实物理接口，过滤 Docker / VPN / 虚拟机等虚拟接口。
 * 返回去重的 IP 列表（可能跨多个网段）。
 */
function localIpv4List() {
  const nets = os.networkInterfaces()
  const VIRTUAL_RE = /^(docker|br-|veth|vmnet|utun|awdl|llw|anpi|bridge|lo|virbr|vbox|tun|tap|tailscale|wg)/i
  // macOS Wi-Fi = en0；Windows Wi-Fi = 'Wi-Fi' / 'WLAN'；以太网 = 'Ethernet' / '以太网'
  const PREFERRED_RE = /^(en0|en1|eth|Wi-Fi|WLAN|Ethernet|以太网|无线)/i

  const preferred = []
  const others = []
  for (const [name, addrs] of Object.entries(nets)) {
    if (VIRTUAL_RE.test(name)) continue
    for (const a of addrs) {
      if (a.family !== 'IPv4' || a.internal) continue
      const entry = { name, ip: a.address }
      if (PREFERRED_RE.test(name)) preferred.push(entry)
      else others.push(entry)
    }
  }
  // Deduplicate by IP, preferred first
  const seen = new Set()
  const result = []
  for (const e of [...preferred, ...others]) {
    if (!seen.has(e.ip)) {
      seen.add(e.ip)
      result.push(e.ip)
    }
  }
  return result
}

/**
 * 局域网自动发现主设备：扫描本机所有候选网段 .1–.254 的 :8000/api/health，
 * 校验响应含 "app":"hhz-data-service"，返回第一个命中的基地址。
 * 改进：遍历所有本机网段（解决多网卡选错接口）；超时提升到 800ms（解决 Wi-Fi 误超时）。
 */
async function discoverHost() {
  const ips = localIpv4List()
  if (!ips.length) return null

  // Collect unique subnets to scan
  const selfIps = new Set(ips)
  const subnets = []
  const seenBases = new Set()
  for (const ip of ips) {
    const parts = ip.split('.')
    if (parts.length !== 4) continue
    const base = parts.slice(0, 3).join('.')
    if (seenBases.has(base)) continue
    seenBases.add(base)
    subnets.push(base)
  }
  if (!subnets.length) return null

  const CONCURRENCY = 50
  const TIMEOUT_MS = 800

  let found = null
  // Build flat list of all IPs to probe
  const targets = []
  for (const base of subnets) {
    for (let i = 1; i <= 254; i++) {
      const candidate = `${base}.${i}`
      if (selfIps.has(candidate)) continue
      targets.push(candidate)
    }
  }

  let cursor = 0
  const worker = async () => {
    while (cursor < targets.length && !found) {
      const ip = targets[cursor++]
      if (found) return
      const url = `http://${ip}:8000/api/health`
      try {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
        const res = await net.fetch(url, { signal: controller.signal })
        clearTimeout(timer)
        if (res.ok) {
          const body = await res.json().catch(() => ({}))
          if (body.app === 'hhz-data-service') {
            found = `http://${ip}:8000`
            return
          }
        }
      } catch {
        /* 未响应/非目标服务，忽略 */
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()))
  return found
}

app.whenReady().then(() => {
  // 本地缓存图片协议：app-img://cache/<相对路径>
  protocol.handle('app-img', async (request) => {
    const url = new URL(request.url)
    if (url.hostname !== 'cache') {
      return new Response('Not Found', { status: 404 })
    }
    const rel = decodeURIComponent(url.pathname.replace(/^\//, ''))
    let file
    try {
      file = safeJoin(imageCacheDir(), rel)
    } catch {
      return new Response('Forbidden', { status: 403 })
    }
    try {
      const data = await fs.promises.readFile(file)
      const mime = MIME[path.extname(file).toLowerCase()] || 'application/octet-stream'
      return new Response(data, {
        headers: { 'content-type': mime, 'cache-control': 'public, max-age=31536000, immutable' }
      })
    } catch {
      return new Response('Not Found', { status: 404 })
    }
  })

  // IPC：前端启动时同步图片
  ipcMain.handle('hhz:image-sync', (_event, backendBase) => syncImages(backendBase))

  // IPC：按相对路径返回本地缓存可访问 URL（app-img://cache/...），不存在返回 ''
  ipcMain.handle('hhz:image-resolve', (_event, rel) => {
    try {
      const local = safeJoin(imageCacheDir(), String(rel || '').replace(/^uploads\//, ''))
      if (fs.existsSync(local)) {
        return `app-img://cache/${String(rel || '').replace(/^uploads\//, '')}`
      }
    } catch {
      /* ignore */
    }
    return ''
  })

  // IPC：局域网自动发现主设备，返回基地址或 null
  ipcMain.handle('hhz:discover-host', () => discoverHost())

  // IPC：目录缓存读写（/api/sync 结果，离线兜底）
  ipcMain.handle('hhz:catalog-cache-read', () => {
    try {
      return JSON.parse(fs.readFileSync(catalogCacheFile(), 'utf8'))
    } catch {
      return null
    }
  })
  ipcMain.handle('hhz:catalog-cache-write', (_event, payload) => {
    try {
      fs.writeFileSync(catalogCacheFile(), JSON.stringify(payload))
      return true
    } catch {
      return false
    }
  })

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
