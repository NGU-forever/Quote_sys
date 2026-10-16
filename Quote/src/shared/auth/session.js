/**
 * 销售端登录会话（纯逻辑，无框架依赖，可直接单测）。
 *
 * 令牌沿用工作台的 localStorage 键 `quote_workbench_token`，因此与
 * `shared/api/http.js` 的 `createHttp({ withToken: true })` 天然打通，
 * 也复用同一套 JWT —— 后端无需新增接口：
 * 员工账号由管理员在 Workbench「员工管理」创建，`role` 默认 `sales`，
 * `POST /api/auth/login` 对角色不做限制。
 *
 * 会话状态三态：
 * - 已登录：有令牌，可提交服务端单据（官方单号）。
 * - 离线使用：无令牌但用户显式选择离线，只做本地草稿（拿不到官方单号）。
 * - 未登录：无令牌且未选择离线 → 路由守卫送到登录页。
 */

export const TOKEN_KEY = 'quote_workbench_token'
export const LEGACY_TOKEN_KEY = 'hhz_workbench_token'
export const USER_KEY = 'quote_sales_user'
export const OFFLINE_KEY = 'quote_offline_use'

function store() {
  try {
    return globalThis.localStorage || null
  } catch {
    return null
  }
}

export function readToken() {
  const s = store()
  if (!s) return ''
  return s.getItem(TOKEN_KEY) || s.getItem(LEGACY_TOKEN_KEY) || ''
}

export function hasToken() {
  return Boolean(readToken())
}

/** 登录成功：写入令牌与用户名，并退出离线模式。 */
export function writeSession(token, username = '') {
  const s = store()
  if (!s) return
  s.setItem(TOKEN_KEY, String(token || ''))
  s.removeItem(LEGACY_TOKEN_KEY)
  if (username) s.setItem(USER_KEY, String(username))
  s.removeItem(OFFLINE_KEY)
}

/** 退出登录 / 令牌失效：清空令牌与用户名（不影响离线标记，由调用方决定）。 */
export function clearSession() {
  const s = store()
  if (!s) return
  s.removeItem(TOKEN_KEY)
  s.removeItem(LEGACY_TOKEN_KEY)
  s.removeItem(USER_KEY)
}

export function readUsername() {
  const s = store()
  return (s && s.getItem(USER_KEY)) || ''
}

export function isOfflineMode() {
  const s = store()
  return Boolean(s && s.getItem(OFFLINE_KEY))
}

export function setOfflineMode() {
  const s = store()
  if (s) s.setItem(OFFLINE_KEY, '1')
}

export function clearOfflineMode() {
  const s = store()
  if (s) s.removeItem(OFFLINE_KEY)
}

/** 登录失败提示：区分「账号密码错」与「连不上主设备」两类可照做的动作。 */
export function describeLoginError(error) {
  const message = String((error && error.message) || error || '')
  if (message.includes('用户名或密码')) {
    return '用户名或密码错误，请确认后重试；忘记密码可让管理员在工作台重置。'
  }
  if (message.includes('无法连接后端服务')) {
    return '连不上主设备：请确认主设备已开机并在同一局域网，或在下方填写正确的服务器地址。'
  }
  return message || '登录失败，请重试。'
}
