<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Boxes,
  History,
  Package,
  PackageCheck,
  Stethoscope
} from 'lucide-vue-next'
import { useCatalogStore } from '../../shared/stores/catalog'
import { useQuoteStore } from '../stores/quote'
import { useToast } from '../../shared/composables/useToast'
import { formatMoney } from '../../shared/utils/format'
import logoUrl from '../assets/克夫尼.jpg'

import ProductConfigPanel from './ProductConfigPanel.vue'
import QuoteResultsPanel from './QuoteResultsPanel.vue'
import ExportQuoteModal from './ExportQuoteModal.vue'
import HistoryQuotesModal from './HistoryQuotesModal.vue'

const quote = useQuoteStore()
const catalog = useCatalogStore()
const toast = useToast()

const printFrame = ref(null)
const showExportModal = ref(false)
const showHistoryModal = ref(false)

const directPackage = computed(() => quote.activePackage)
const directPackageSets = computed(() => quote.packageSets)
const directPackageValid = computed(() => {
  const price = Number(directPackage.value?.price) || 0
  return Boolean(directPackage.value && price > 0 && quote.packageModeRows.length > 0)
})

const modes = computed(() => {
  const hasDevices = catalog.deviceList.length > 0
  const hasConsumables = catalog.consumableList.length > 0
  const base = []
  if (hasDevices && hasConsumables) {
    base.push({ id: 'both', label: '同时购买', desc: '设备 + 耗材', icon: Boxes })
  }
  if (hasConsumables) {
    base.push({ id: 'consumables', label: '仅购耗材', desc: '阶梯折算', icon: Package })
  }
  if (hasDevices) {
    base.push({ id: 'equipment', label: '仅购设备', desc: '单机采购', icon: Stethoscope })
  }
  if (quote.packageOptions.length > 0) {
    base.push({ id: 'package', label: '套餐整购', desc: '整套购买', icon: PackageCheck })
  }
  return base
})

watch(
  () => modes.value.map((mode) => mode.id).join(','),
  (ids) => {
    if (!ids) return
    const list = ids.split(',')
    if (!list.includes(quote.purchaseMode)) {
      quote.setPurchaseMode(list[0])
    }
  }
)

const bannerText = computed(() => {
  if (quote.purchaseMode === 'package') {
    if (!directPackage.value) return '暂无固定整购套餐，请先在 Workbench 配置后重新同步'
    if (!directPackageValid.value) {
      return '套餐价格或 SKU 组成未完整，请先在 Workbench 补全'
    }
    return `按 Workbench 套餐整购：${directPackageSets.value} 套 × ${formatMoney(
      directPackage.value.price
    )}`
  }
  if (quote.purchaseMode === 'consumables') {
    return `当前阶梯单价 ${formatMoney(quote.plan1UnitPrice, 1)}/${catalog.selectedConsumable?.unit || '袋'}`
  }
  if (quote.purchaseMode === 'equipment') {
    return `当前设备：${catalog.selectedDevice?.name || '未选择设备'}`
  }
  if (!quote.hasPackage) {
    return '该设备 + 耗材组合不在套餐定义表中，仅支持单独采购，无最佳方案对比'
  }
  if (quote.packagePlans.some((plan) => !plan.valid)) {
    return '套餐参数未完整同步，请在 Workbench 补全价格与组成后重新同步'
  }
  if (!quote.packagePlans.some((plan) => plan.eligible)) {
    return `套餐方案需至少 ${quote.packagePlans[0]?.minBoxes ?? 2} 箱起购，当前箱数不足`
  }
  if (quote.saving > 0) {
    return `方案${quote.bestPackagePlan.planNo}比方案1节省 ${formatMoney(quote.saving)}`
  }
  return '当前方案1更划算'
})

function selectPurchaseMode(mode) {
  quote.setPurchaseMode(mode)
  if (mode === 'package' && quote.packageOptions.length > 0 && !quote.activePackage) {
    quote.selectPackage(quote.packageOptions[0].id)
  }
}

function handleSaveDraft() {
  const saved = quote.saveQuote()
  toast.push(`已保存当前报价草稿（单号 ${saved.id}）`, 'success')
}

function handleRestore(item) {
  quote.restoreQuote(item)
  showHistoryModal.value = false
  toast.push(`已恢复报价单号 ${item.id} 的选配参数`, 'success')
}

function onExported() {
  toast.push('已生成正式报价单', 'info')
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (showExportModal.value) showExportModal.value = false
    if (showHistoryModal.value) showHistoryModal.value = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <section id="quote" class="section quote-page">
    <div class="quote-deco" aria-hidden="true">
      <span class="deco-dots"></span>
      <span class="deco-ring ring-1"></span>
      <span class="deco-ring ring-2"></span>
    </div>

    <div class="section-inner dashboard-layout">
      <!-- 紧凑工作台顶栏：标题、模式定位与历史草稿快捷入口 -->
      <div class="quote-header-bar">
        <div class="header-titles">
          <div class="title-row">
            <h2 class="workspace-title">QuoteSys 商业价格计算器</h2>
          </div>
          <p class="workspace-sub">
            实时多方案测算 · 阶梯量价分析 · 一键生成规范盖章报价单
          </p>
        </div>

        <div class="header-tools">
          <button
            class="btn btn-sm btn-outline history-btn"
            type="button"
            title="查看本地保存的报价草稿"
            @click="showHistoryModal = true"
          >
            <History :size="15" />
            <span>报价历史</span>
            <span v-if="quote.savedQuotes.length > 0" class="history-count-badge">
              {{ quote.savedQuotes.length }}
            </span>
          </button>
        </div>
      </div>

      <!-- 采购模式分段切换器（置顶第一因果层级，彻底消除模式切换引起的布局抖动） -->
      <div class="mode-switcher-card">
        <div class="mode-switcher-nav">
          <button
            v-for="mode in modes"
            :key="mode.id"
            type="button"
            class="mode-nav-btn"
            :class="{ active: quote.purchaseMode === mode.id }"
            @click="selectPurchaseMode(mode.id)"
          >
            <component :is="mode.icon" :size="18" />
            <span class="mode-nav-texts">
              <strong class="mode-nav-label">{{ mode.label }}</strong>
              <small class="mode-nav-desc">{{ mode.desc }}</small>
            </span>
          </button>
        </div>
      </div>

      <!-- 双栏仪表盘：左侧高内聚配置卡片 / 右侧对比与结算方案 -->
      <div class="dashboard-grid">
        <div class="dashboard-left">
          <ProductConfigPanel />
        </div>

        <div class="dashboard-right">
          <QuoteResultsPanel
            :banner-text="bannerText"
            @export="showExportModal = true"
            @save-draft="handleSaveDraft"
          />
        </div>
      </div>
    </div>
  </section>

  <!-- 导出报价单弹窗 -->
  <ExportQuoteModal
    v-model="showExportModal"
    :logo-url="logoUrl"
    :iframe-el="printFrame"
    @exported="onExported"
  />

  <!-- 本地历史报价草稿弹窗 -->
  <HistoryQuotesModal
    v-model="showHistoryModal"
    @restore="handleRestore"
  />

  <iframe ref="printFrame" class="quote-print-frame" title="报价单打印"></iframe>
</template>

<style scoped>
.quote-page {
  position: relative;
  overflow: hidden;
  min-height: calc(100vh - 72px);
  padding: 24px 0 60px;
  background:
    radial-gradient(960px 520px at 104% -12%, rgba(100, 181, 246, 0.18), transparent 62%),
    radial-gradient(820px 460px at -8% 112%, rgba(30, 136, 229, 0.14), transparent 60%),
    linear-gradient(180deg, #f0f7ff 0%, #e6f1fc 52%, #f2f8ff 100%);
}

.quote-page .section-inner {
  position: relative;
  z-index: 1;
}

.quote-deco {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.deco-dots {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(30, 136, 229, 0.12) 1px, transparent 1px);
  background-size: 28px 28px;
  opacity: 0.45;
  mask-image: radial-gradient(ellipse 120% 100% at 50% 30%, #000 30%, transparent 75%);
}

.deco-ring {
  position: absolute;
  border-radius: 50%;
  border: 1.5px solid rgba(30, 136, 229, 0.14);
}
.ring-1 { width: 320px; height: 320px; right: -120px; top: -140px; }
.ring-2 { width: 520px; height: 520px; right: -220px; top: -240px; }

/* 紧凑顶栏 */
.quote-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
  padding: 4px 2px;
}

.header-titles {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--primary-light);
  color: var(--primary-dark);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.workspace-title {
  font-size: 24px;
  font-weight: 800;
  color: var(--text);
  margin: 0;
  line-height: 1.2;
}

.workspace-sub {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
}

.history-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
}

.history-count-badge {
  display: inline-grid;
  place-items: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}

/* 采购模式分段导航卡片 */
.mode-switcher-card {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 8px;
  margin-bottom: 22px;
  box-shadow: 0 10px 24px -18px rgba(13, 71, 161, 0.35);
}

.mode-switcher-nav {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.mode-nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-nav-btn:hover {
  background: #f8fafc;
  color: var(--text);
}

.mode-nav-btn.active {
  background: #fff;
  border-color: rgba(30, 136, 229, 0.3);
  color: var(--primary-dark);
  box-shadow: 0 4px 14px rgba(30, 136, 229, 0.15);
}

.mode-nav-texts {
  display: flex;
  flex-direction: column;
  text-align: left;
  line-height: 1.25;
}

.mode-nav-label {
  font-size: 14px;
  font-weight: 700;
}

.mode-nav-desc {
  font-size: 11px;
  color: var(--muted);
  margin-top: 2px;
}

.mode-nav-btn.active .mode-nav-desc {
  color: var(--primary);
}

@media (max-width: 768px) {
  .mode-switcher-nav {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  .mode-nav-btn {
    padding: 10px 12px;
  }
}

@media (max-width: 480px) {
  .mode-switcher-card {
    padding: 6px;
    margin-bottom: 16px;
  }
  .mode-nav-btn {
    padding: 8px 10px;
    gap: 8px;
  }
  .mode-nav-label {
    font-size: 13px;
  }
  .mode-nav-desc {
    font-size: 10px;
  }
}

/* 双栏仪表盘网格 */
.dashboard-grid {
  display: grid;
  grid-template-columns: 460px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

@media (min-width: 1366px) {
  .workspace-title {
    font-size: 26px;
  }
  .workspace-sub {
    font-size: 14px;
  }
  .mode-nav-btn {
    padding: 14px 16px;
  }
  .mode-nav-label {
    font-size: 15px;
  }
  .dashboard-grid {
    grid-template-columns: 500px minmax(0, 1fr);
    gap: 28px;
  }
}

@media (min-width: 1536px) {
  .workspace-title {
    font-size: 28px;
  }
  .mode-nav-btn {
    padding: 15px 18px;
  }
  .dashboard-grid {
    grid-template-columns: 540px minmax(0, 1fr);
    gap: 32px;
  }
}

@media (min-width: 1720px) {
  .dashboard-grid {
    grid-template-columns: 570px minmax(0, 1fr);
    gap: 36px;
  }
}

@media (max-width: 980px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

.quote-print-frame {
  position: fixed;
  right: 0;
  bottom: 0;
  width: 0;
  height: 0;
  border: 0;
}
</style>
