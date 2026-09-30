// src/shared/api/http.js
// 请求工厂：为各系统 client 提供统一的 fetch 封装，不携带任何业务方法。
// - withToken=true 时自动附加工作台 token（仅工作台 client 使用）；
// - 401 时自动清除失效 token（仅 withToken 模式）。
// 管理接口不存在于此文件，全部由调用方 client 组装。
import { getApiBase } from '../utils/backendConfig'

const TOKEN_KEY = 'hhz_workbench_token'

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

function qs(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const str = search.toString()
  return str ? `?${str}` : ''
}

/** 创建请求函数。withToken=true 时自动附加/清理工作台 token。 */
export function createHttp({ withToken = false } = {}) {
  async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) }
    // FormData 由浏览器自动设置 multipart 边界，不手动指定 Content-Type
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json'
    }
    if (withToken) {
      const token = getToken()
      if (token) headers.Authorization = `Bearer ${token}`
    }

    let res
    try {
      res = await fetch(`${getApiBase()}${path}`, { ...options, headers })
    } catch {
      throw new Error('无法连接后端服务，请确认后端已启动（npm run dev:server），或在登录页配置服务器地址')
    }

    if (res.status === 401 && withToken) clearToken()

    let data = {}
    try {
      data = await res.json()
    } catch {
      // 非 JSON 响应忽略
    }
    if (!res.ok) throw new Error(data.error || `请求失败（${res.status}）`)
    return data
  }

  // 供工作台 client 复用 token 工具
  request._token = { getToken, setToken: (t) => localStorage.setItem(TOKEN_KEY, t), clearToken, hasToken: () => Boolean(getToken()) }
  request._qs = qs
  return request
}
