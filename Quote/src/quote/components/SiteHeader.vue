<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import HostSettings from './HostSettings.vue'
import { useSettingsStore } from '../../shared/stores/settings'
import fallbackLogo from '../assets/克夫尼.jpg'

const router = useRouter()
const settingsStore = useSettingsStore()

const brandName = computed(() => settingsStore.company?.name || 'QuoteSys 商业报价平台')
const logoSrc = computed(() => settingsStore.company?.logo || fallbackLogo)

function goToDesigner() {
  router.push('/designer')
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
        <button class="nav-designer-btn" title="打开界面设计器" @click="goToDesigner">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 20h9"/>
            <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
          </svg>
          设计器
        </button>
        <HostSettings />
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

.nav-designer-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 600;
  color: #3b82f6;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 7px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.nav-designer-btn:hover {
  background: #dbeafe;
  color: #1d4ed8;
}
</style>
