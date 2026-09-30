// src/stores/auth.js
import { defineStore } from 'pinia'
import { api, clearToken, getToken, setToken } from '../api/workbenchClient'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken(),
    user: null
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token)
  },
  actions: {
    async login(username, password) {
      const { token, user } = await api.login(username, password)
      setToken(token)
      this.token = token
      this.user = user
      return user
    },
    async register(username, password) {
      const { token, user } = await api.register(username, password)
      setToken(token)
      this.token = token
      this.user = user
      return user
    },
    logout() {
      clearToken()
      this.token = ''
      this.user = null
    },
    async fetchMe() {
      if (!this.token) return null
      try {
        const { user } = await api.me()
        this.user = user
        return user
      } catch {
        this.logout()
        return null
      }
    },
    async fetchSetupStatus() {
      return api.authStatus()
    }
  }
})
