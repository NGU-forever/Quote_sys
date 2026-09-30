// src/utils/imageSync.js
// 产品图片本地缓存同步。
//
// 与目录同步（catalog.hydrateFromRemote）一致：母版单向同步——只从后端拉取覆盖，
// 绝不把本地改动写回服务器。后端可能部署在远程服务器，管理员通过文件管理工具
// 随时往服务器 uploads 目录更新图片，前端每次开启时据此同步到本机缓存。
//
// - Electron 环境：调用主进程把后端 uploads 目录图片下载到 <userData>/image-cache，
//   图片以 app-img:// 协议从本地读取（离线可用），resolveImage 命中本地缓存即返回本地 URL。
// - Web 环境：无本地磁盘，直接使用后端远程地址（浏览器自带 HTTP 缓存）。
import { reactive } from 'vue'
import { getBackendBase } from './backendConfig'

function getBridge() {
  if (typeof window === 'undefined') return null
  return window.quoteAPI || window.hhzAPI || null
}

export const isElectron =
  typeof window !== 'undefined' && Boolean(getBridge() && getBridge().isElectron)

const state = reactive({
  // 已成功缓存到本地的相对路径集合（如 products/p1693123456789.jpg）
  localFiles: new Set(),
  syncing: false,
  lastSync: null
})

export function imageCacheState() {
  return state
}

/** 启动时同步后端图片到本地缓存（Electron 生效；Web 下自动跳过）。 */
export function syncImages() {
  const bridge = getBridge()
  if (!isElectron || !bridge?.syncImages) return Promise.resolve({ ok: false, skipped: true })
  if (state.syncing) return state.lastSync
  state.syncing = true
  state.lastSync = bridge
    .syncImages(getBackendBase())
    .then((result) => {
      if (result && Array.isArray(result.files)) {
        state.localFiles = new Set(result.files)
      }
      return result
    })
    .finally(() => {
      state.syncing = false
    })
  return state.lastSync
}

/**
 * 把产品 image 字段解析为可渲染的 src（响应式：图片同步完成后自动切到本地缓存）。
 * - 绝对 URL / data / blob / app-img 原样返回；
 * - 相对路径（/uploads/products/xxx.jpg）：
 *   Electron 下本地已缓存 → app-img://cache/<相对路径>（离线可用）；
 *   未缓存或 Web 环境 → 后端远程地址（支持配置的服务器地址）。
 */
export function resolveImage(src) {
  if (!src) return ''
  if (/^(https?:|data:|blob:|app-img:)/i.test(src)) return src
  const rel = src.replace(/^\/+/, '').replace(/^uploads\//, '')
  if (isElectron && state.localFiles.has(rel)) {
    // 逐段编码（保留 / 层级），主进程侧做 decodeURIComponent 还原
    return `app-img://cache/${rel.split('/').map(encodeURIComponent).join('/')}`
  }
  return `${getBackendBase()}/uploads/${rel}`
}
