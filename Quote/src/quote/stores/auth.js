import { defineStore } from 'pinia'
import { createHttp } from '../../shared/api/http'
import {
  clearOfflineMode,
  clearSession,
  hasToken,
  isOfflineMode,
  readUsername,
  setOfflineMode,
  writeSession,
} from '../../shared/auth/session'

// 登录本身不带令牌：避免「登录失败」被误当成「令牌失效」而清掉已有会话。
const anonymous = createHttp({ withToken: false })
// 校验令牌与业务写入都需要令牌。
const authed = createHttp({ withToken: true })

export const useAuthStore = defineStore('sales-auth', {
  state: () => ({
    username: readUsername(),
    authed: hasToken(),
    // 离线使用 = 无令牌但用户显式选择离线开单（只有本地草稿，没有官方单号）
    offline: !hasToken() && isOfflineMode()
  }),
  getters: {
    displayName: (state) => (state.offline ? '离线使用' : state.username || '')
  },
  actions: {
    async login(username, password) {
      const data = await anonymous('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      })
      const name = (data && data.user && data.user.username) || username
      writeSession(data && data.token, name)
      this.username = name
      this.authed = true
      this.offline = false
      return name
    },

    /** 主设备不可达时的逃生通道：仍可算价与存本地草稿，但拿不到官方单号。 */
    continueOffline() {
      setOfflineMode()
      clearSession()
      this.username = ''
      this.authed = false
      this.offline = true
    },

    logout() {
      clearSession()
      clearOfflineMode()
      this.username = ''
      this.authed = false
      this.offline = false
    },

    /**
     * 校验令牌是否仍然有效。
     * - 'ok'：有效（含未登录/离线状态，无需校验）
     * - 'expired'：鉴权失败，已清会话 → 调用方应送回登录页
     * - 'unreachable'：连不上主设备，**保留会话**，避免网络抖动把员工踢下线
     */
    async verify() {
      if (!this.authed) return 'ok'
      try {
        await authed('/auth/me')
        return 'ok'
      } catch (err) {
        const message = String((err && err.message) || '')
        if (message.includes('无法连接后端服务')) return 'unreachable'
        clearSession()
        this.username = ''
        this.authed = false
        this.offline = false
        return 'expired'
      }
    }
  }
})
