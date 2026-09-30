// src/utils/catalogCache.js
// 目录本地缓存：把 /api/sync 返回的 { catalog, settings, rev, updated_at } 持久化到本机，
// 主设备离线时据此兜底。Electron 走主进程 IPC 写 <userData>/catalog-cache.json；
// Web 环境走 localStorage（无本地磁盘）。
import { isElectron } from './imageSync'

const CACHE_KEY = 'quote_catalog_cache'
const LEGACY_CACHE_KEY = 'hhz_catalog_cache'

function getBridge() {
  if (typeof window === 'undefined') return null
  return window.quoteAPI || window.hhzAPI || null
}

function readLocal() {
  try {
    const raw = localStorage.getItem(CACHE_KEY) || localStorage.getItem(LEGACY_CACHE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeLocal(payload) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(payload))
  } catch {
    /* ignore */
  }
}

/** 读取本地缓存，缺失/损坏返回 null */
export async function loadCatalogCache() {
  const bridge = getBridge()
  if (isElectron && bridge?.readCatalogCache) {
    try {
      return await bridge.readCatalogCache()
    } catch {
      return null
    }
  }
  return readLocal()
}

/** 写入本地缓存（Electron 落盘；Web 落 localStorage） */
export async function saveCatalogCache(payload) {
  const bridge = getBridge()
  if (isElectron && bridge?.writeCatalogCache) {
    try {
      await bridge.writeCatalogCache(payload)
    } catch {
      /* ignore */
    }
    return
  }
  writeLocal(payload)
}
