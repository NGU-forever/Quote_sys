// src/utils/backendConfig.js
// 后端服务器地址配置（支持远程服务器部署场景）：
// 优先读取本机 localStorage 中配置的地址；
// 未配置时回退构建环境变量 VITE_API_BASE_URL，再回退本地开发默认值。
const BASE_KEY = 'quote_backend_base'
const LEGACY_BASE_KEY = 'hhz_backend_base'

export function getBackendBase() {
  const saved = localStorage.getItem(BASE_KEY) || localStorage.getItem(LEGACY_BASE_KEY)
  if (saved) return saved.replace(/\/+$/, '')
  const env = import.meta.env.VITE_API_BASE_URL
  return (env || 'http://localhost:8000').replace(/\/+$/, '')
}

export function setBackendBase(url) {
  const base = String(url || '')
    .trim()
    .replace(/\/+$/, '')
  if (base) {
    localStorage.setItem(BASE_KEY, base)
    return base
  }
  localStorage.removeItem(BASE_KEY)
  localStorage.removeItem(LEGACY_BASE_KEY)
  return getBackendBase()
}

/** API 基础路径：配置了服务器地址 → {base}/api；否则走 Vite 代理 /api */
export function getApiBase() {
  const saved = localStorage.getItem(BASE_KEY) || localStorage.getItem(LEGACY_BASE_KEY)
  if (saved) return `${saved.replace(/\/+$/, '')}/api`
  return import.meta.env.VITE_API_BASE || '/api'
}
