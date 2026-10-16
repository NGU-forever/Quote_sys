<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { LogOut } from 'lucide-vue-next'
import HostSettings from './HostSettings.vue'
import { useSettingsStore } from '../../shared/stores/settings'
import { useAuthStore } from '../stores/auth'
import fallbackLogo from '../assets/克夫尼.jpg'

const router = useRouter()
const settingsStore = useSettingsStore()
const auth = useAuthStore()

const brandName = computed(() => settingsStore.company?.name || 'QuoteSys 商业报价平台')
const logoSrc = computed(() => settingsStore.company?.logo || fallbackLogo)

function handleLogout() {
  if (!confirm('退出登录后将无法提交服务端单据（拿不到官方单号），确定退出吗？')) return
  auth.logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <header class="landing-header">
    <div class="header-inner">
      <div class="brand">
        <img class="brand-logo" :src="logoSrc" :alt="brandName" />
        <div class="brand-copy">
          <div class="brand-title-row">
            <span class="brand-name">{{ brandName }}</span>
            <span class="brand-version-badge">v2.0.0</span>
          </div>
        </div>
      </div>

      <nav class="main-nav">
        <HostSettings />
        <div v-if="auth.displayName" class="user-chip" :class="{ offline: auth.offline }">
          <span class="user-name" :title="auth.offline ? '未登录，仅本地草稿' : '当前登录账号'">
            {{ auth.displayName }}
          </span>
          <button class="user-logout" type="button" aria-label="退出登录" @click="handleLogout">
            <LogOut :size="14" />
          </button>
        </div>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.brand-logo {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  object-fit: cover;
  flex: none;
  box-shadow: 0 8px 16px -10px rgba(13, 71, 161, 0.5);
}

.brand-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-version-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 6px;
  background: var(--primary-light);
  color: var(--primary-dark);
  line-height: 1.3;
}

.main-nav {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 当前登录账号（或离线标记）+ 退出 */
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 6px 5px 12px;
  border-radius: 999px;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
}

.user-chip.offline {
  background: #fefce8;
  border-color: #fde68a;
  color: #a16207;
}

.user-name {
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-logout {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: transparent;
  border: none;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.user-logout:hover {
  background: var(--rose-light);
  color: var(--rose);
}
</style>
