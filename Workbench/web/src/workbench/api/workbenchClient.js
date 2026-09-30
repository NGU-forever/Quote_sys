// src/workbench/api/workbenchClient.js
// 工作台（主系统前端）API 客户端 —— 全项目唯一持有 token 与全部管理（读写）接口的模块。
//
// 【引用边界】只允许 src/workbench/ 下的代码引用本文件；
// 报价版（src/quote/）与共享只读层（src/shared/）一律使用 shared/api/quoteClient.js（只读）。
import { createHttp } from '../../shared/api/http'

const TOKEN_KEY = 'quote_workbench_token'
const LEGACY_TOKEN_KEY = 'hhz_workbench_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY) || ''
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(LEGACY_TOKEN_KEY)
}

export function hasToken() {
  return Boolean(getToken())
}

const request = createHttp({ withToken: true })

export const api = {
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  register: (username, password) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  authStatus: () => request('/auth/status'),
  accounts: () => request('/auth/accounts'),
  resetPassword: (username, newPassword) =>
    request('/auth/reset-password', { method: 'POST', body: JSON.stringify({ username, new_password: newPassword, newPassword }) }),
  me: () => request('/auth/me'),
  // 报价管理与详情
  listQuotes: (params = {}) =>
    request('/quotes' + (Object.keys(params).length ? '?' + new URLSearchParams(params).toString() : '')),
  getQuote: (quoteNo) => request('/quotes/' + quoteNo),
  // 员工与权限管理
  listEmployees: (params = {}) =>
    request('/admin/employees' + (Object.keys(params).length ? '?' + new URLSearchParams(params).toString() : '')),
  createEmployee: (payload) =>
    request('/admin/employees', { method: 'POST', body: JSON.stringify(payload) }),
  updateEmployee: (id, payload) =>
    request(`/admin/employees/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  // 公开目录/同步负载（工作台进入时也用于刷新「母版目录」，只读拉取）
  getCatalog: () => request('/catalog'),
  getSync: () => request('/sync'),
  listProducts: (params = {}) => request(`/products${qs(params)}`),
  createProduct: (payload) => request('/products', { method: 'POST', body: JSON.stringify(payload) }),
  updateProduct: (id, payload) =>
    request(`/products/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteProduct: (id) => request(`/products/${id}`, { method: 'DELETE' }),
  /**
   * 维护设备-耗材绑定（双向，整体替换）：
   * - 设备：{ consumable_sku_ids: [...] }；耗材：{ device_sku_ids: [...] }；
   * 空数组 = 解除绑定（自由搭配）。
   */
  updateProductBindings: (id, payload) =>
    request(`/products/${id}/bindings`, { method: 'PUT', body: JSON.stringify(payload) }),
  /** 上传产品照片（multipart 字段名 file），返回更新后的产品 */
  uploadProductPhoto: (id, file) => {
    const form = new FormData()
    form.append('file', file)
    return request(`/products/${id}/photo`, { method: 'POST', body: form })
  },
  // 基本设置（公司信息 + 报价参数），工作台「基本设置」页使用
  getSettings: () => request('/settings'),
  updateSettings: (payload) => request('/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  listPackages: () => request('/packages'),
  createPackage: (payload) =>
    request('/packages', { method: 'POST', body: JSON.stringify(payload) }),
  updatePackage: (id, payload) =>
    request(`/packages/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deletePackage: (id) => request(`/packages/${id}`, { method: 'DELETE' }),
  // 数据生成 Agent（源资料 → 规范化数据库候选）
  agentAssets: () => request('/agent/assets'),
  agentAssetsStatus: () => request('/agent/assets/status'),
  agentUploadAsset: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/agent/assets/upload', { method: 'POST', body: form })
  },
  agentDeleteAsset: (filename) =>
    request(`/agent/assets/${encodeURIComponent(filename)}`, { method: 'DELETE' }),
  agentRuns: () => request('/agent/runs'),
  agentStartRun: (payload = {}) =>
    request('/agent/runs', { method: 'POST', body: JSON.stringify(payload) }),
  agentGetRun: (runId) => request(`/agent/runs/${runId}`),
  agentCancelRun: (runId) =>
    request(`/agent/runs/${runId}/cancel`, { method: 'POST' }),
  // 从检查点续跑（进程异常中断后不必从头再来）
  agentResumeRun: (runId) =>
    request(`/agent/runs/${runId}/resume`, { method: 'POST' }),
  agentApplyRun: (runId, candidates = null) =>
    request(`/agent/runs/${runId}/apply`, {
      method: 'POST',
      body: JSON.stringify(candidates ? { candidates } : {})
    }),
  agentRetryRun: (runId, payload = {}) =>
    request(`/agent/runs/${runId}/retry`, { method: 'POST', body: JSON.stringify(payload) }),
  // AI 模型接口配置（保存后 Agent 运行时优先读取；API Key 不返回原文）
  getAgentConfig: () => request('/agent/config'),
  saveAgentConfig: (payload) =>
    request('/agent/config', { method: 'PUT', body: JSON.stringify(payload) }),
  // 网络诊断（设置页「网络与连接」面板）
  getNetworkDiagnostics: () => request('/network/diagnostics')
}

function qs(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const str = search.toString()
  return str ? `?${str}` : ''
}
