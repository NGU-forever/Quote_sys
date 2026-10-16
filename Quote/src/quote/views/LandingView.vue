<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCatalogStore } from '../../shared/stores/catalog'
import { getApiBase } from '../../shared/utils/backendConfig'
import SiteHeader from '../components/SiteHeader.vue'
import QuoteSection from '../components/QuoteSection.vue'
import ThemeProvider from '../../renderer/tokens/ThemeProvider.vue'
import LayoutEngine from '../../renderer/LayoutEngine.vue'

const router = useRouter()
const catalog = useCatalogStore()

const activeSpec = ref(null)
const useClassicView = ref(false)

// 检查后端是否有已定稿的 UiSpec
async function checkActiveSpec() {
  try {
    const apiBase = getApiBase()
    const res = await fetch(`${apiBase}/designer/spec`)
    if (res.ok) {
      const data = await res.json()
      if (data && data.payload) {
        activeSpec.value = data.payload
      }
    }
  } catch {
    // 离线或后端未配置时保持默认
  }
}

function toggleView() {
  useClassicView.value = !useClassicView.value
}

function goToDesigner() {
  router.push('/designer')
}

onMounted(() => {
  catalog.hydrateFromRemote()
  checkActiveSpec()
})
</script>

<template>
  <SiteHeader />
  <main>
    <!-- 如果后端已定稿 UiSpec 且用户未主动切回经典视图，直接呈现定制化渲染界面 -->
    <template v-if="activeSpec && !useClassicView">
      <ThemeProvider
        :preset-id="activeSpec.style?.preset_id"
        :tokens="activeSpec.style?.tokens"
      >
        <div class="custom-spec-banner">
          <div class="banner-info">
            <span class="badge">已激活定制界面</span>
            <span class="spec-name">{{ activeSpec.meta?.name || '企业定制方案' }}</span>
          </div>
          <div class="banner-actions">
            <button class="btn-text" @click="toggleView">切换至经典计算器</button>
            <button class="btn-outline" @click="goToDesigner">修改设计</button>
          </div>
        </div>
        <LayoutEngine
          :spec="activeSpec"
          :screen="activeSpec.screens?.[0] || {}"
        />
      </ThemeProvider>
    </template>

    <!-- 默认/经典阶梯比价开单页面 -->
    <template v-else>
      <div v-if="activeSpec" class="return-spec-banner">
        <span>当前显示经典计算器模式</span>
        <button class="btn-text" @click="toggleView">返回定制界面</button>
      </div>
      <QuoteSection />
    </template>
  </main>
</template>

<style scoped>
.custom-spec-banner,
.return-spec-banner {
  max-width: 1200px;
  margin: 12px auto 0;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
}

.banner-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.badge {
  background: #10b981;
  color: white;
  padding: 2px 8px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
}

.spec-name {
  color: #334155;
  font-weight: 500;
}

.banner-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-text {
  background: transparent;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 13px;
  text-decoration: underline;
}

.btn-outline {
  background: white;
  border: 1px solid #cbd5e1;
  padding: 3px 10px;
  border-radius: 6px;
  color: #475569;
  cursor: pointer;
  font-size: 12px;
}

.btn-outline:hover {
  background: #f1f5f9;
}
</style>
