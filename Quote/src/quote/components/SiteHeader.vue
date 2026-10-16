<script setup>
import { computed } from 'vue'
import HostSettings from './HostSettings.vue'
import { useSettingsStore } from '../../shared/stores/settings'
import fallbackLogo from '../assets/克夫尼.jpg'

const settingsStore = useSettingsStore()

const brandName = computed(() => settingsStore.company?.name || 'QuoteSys 商业报价平台')
const logoSrc = computed(() => settingsStore.company?.logo || fallbackLogo)
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
</style>
